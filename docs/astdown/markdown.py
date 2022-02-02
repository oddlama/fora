import ast
from dataclasses import dataclass, field
from itertools import zip_longest
from typing import Any, Callable, ContextManager, Optional, Union

import astdown.loader
from astdown.docstring import DocstringSection, parse_numpy_docstring
from astdown.loader import Module, short_docstring

from rich import print as rprint
from rich.markup import escape as rescape

def print(msg: Any, *args, **kwargs):
    rprint(rescape(msg) if isinstance(msg, str) else msg, *args, **kwargs)

separate_each_parameter_in_function = False
include_types_in_signature = True
include_types_in_parameter_descriptions = False
include_defaults_in_parameter_descriptions = False
max_function_signature_width = 76

@dataclass
class _DelegateContextManager:
    f_enter: Callable[[], None]
    f_exit: Callable[[], None]

    def __enter__(self) -> None:
        self.f_enter()

    def __exit__(self, exc_type: Any, exc_value: Any, exc_traceback: Any) -> None:
        _ = (exc_type, exc_value, exc_traceback)
        self.f_exit()

@dataclass
class MarkdownWriter:
    content: str = ""
    title_depth: int = 0
    lists: list = field(default_factory=list)
    needs_bullet_point: bool = False
    indents: list = field(default_factory=list)
    indent_str: str = ""

    def _calculate_indent(self):
        self.indent_str = ''.join(self.indents)

    def margin(self, empty_lines: int):
        existing_newlines = 0
        for c in reversed(self.content):
            if c != "\n":
                break
            existing_newlines += 1
        self.content += max(empty_lines + 1 - existing_newlines, 0) * "\n"

    def add_line(self, line: str):
        indent_prefix = self.indent_str
        if self.needs_bullet_point:
            indent_prefix = ''.join(self.indents[:-1]) + f" {self.lists[-1]}  "
            self.needs_bullet_point = False

        self.content += indent_prefix + line
        if not line.endswith("\n"):
            self.content += "\n"

    def add_content(self, text: str):
        paragraphs = text.split("\n\n")
        for p in paragraphs:
            self.margin(1)
            for line in p.splitlines():
                self.add_line(line)
        self.margin(1)

    def title(self, title: str) -> ContextManager:
        def _enter():
            self.title_depth += 1
            self.margin(1)
            self.add_line("#" * self.title_depth + " " + title)
            self.margin(1)
        def _exit():
            self.title_depth -= 1
        return _DelegateContextManager(_enter, _exit)

    def unordered_list(self, sign: str = "-") -> ContextManager:
        def _enter():
            self.margin(1)
            self.lists.append(sign)
        def _exit():
            self.margin(1)
            self.lists.pop()
        return _DelegateContextManager(_enter, _exit)

    def list_item(self, indent="    ") -> ContextManager:
        def _enter():
            self.indents.append(indent)
            self._calculate_indent()
            self.needs_bullet_point = True
        def _exit():
            self.indents.pop()
            self._calculate_indent()
            if self.needs_bullet_point:
                self.add_line("")
                self.needs_bullet_point = False
        return _DelegateContextManager(_enter, _exit)

def function_def_to_markdown(markdown: MarkdownWriter, func: ast.FunctionDef, parent_basename: Optional[str]) -> None:
    if len(func.args.posonlyargs) > 0:
        raise NotImplementedError(f"functions with 'posonlyargs' are not supported.")

    # Word tokens that need to be joined together, but should be wrapped
    # before overflowing to the right. If the required alignment width
    # becomes too high, we fall back to simple fixed alignment.
    if parent_basename is None:
        initial_str = f"def {func.name}("
    else:
        initial_str = f"def {parent_basename}.{func.name}("
    align_width = len(initial_str)
    if align_width > 32:
        align_width = 8

    def _arg_to_str(arg: ast.arg, default: Optional[ast.expr] = None, prefix: str = ""):
        arg_token = prefix + arg.arg
        equals_separator = "="
        if arg.annotation is not None and include_types_in_signature:
            arg_token += f": {ast.unparse(arg.annotation) or ''}"
            equals_separator = " = "
        if default is not None:
            arg_token += equals_separator + ast.unparse(default) or ""
        return arg_token

    arg: ast.arg
    default: Optional[ast.expr]
    tokens = []
    for arg, default in reversed(list(zip_longest(reversed(func.args.args), reversed(func.args.defaults)))):
        tokens.append(_arg_to_str(arg, default))
    if func.args.vararg is not None:
        tokens.append(_arg_to_str(func.args.vararg, prefix="*"))

    for arg, default in zip(func.args.kwonlyargs, func.args.kw_defaults):
        tokens.append(_arg_to_str(arg, default))
    if func.args.kwarg is not None:
        tokens.append(_arg_to_str(func.args.kwarg, prefix="**"))

    # Append commata to arguments followed by arguments.
    for i,_ in enumerate(tokens[:-1]):
        tokens[i] += ", "

    # Return type or end.
    if func.returns is not None and include_types_in_signature:
        tokens.append(f") -> {ast.unparse(func.returns)}:")
    else:
        tokens.append(f"):")

    markdown.add_line("```python")
    line = initial_str
    def _commit():
        nonlocal line
        if line != "":
            markdown.add_line(line)
            line = ""

    for t in tokens:
        if len(line) + len(t.rstrip()) > max_function_signature_width:
            _commit()

        if line == "":
            line += align_width * " "
        line += t
        if separate_each_parameter_in_function:
            _commit()

    _commit()
    markdown.add_line("```")

def function_parameters_docstring_to_markdown(markdown: MarkdownWriter, func: ast.FunctionDef, decls: dict[str, str]) -> None:
    all_args: dict[str, tuple[ast.arg, Optional[ast.expr]]] = {}
    for arg, default in reversed(list(zip_longest(reversed(func.args.args), reversed(func.args.defaults)))):
        all_args[arg.arg] = (arg, default)
    if func.args.vararg is not None:
        all_args[func.args.vararg.arg] = (func.args.vararg, None)
    for arg, default in zip(func.args.kwonlyargs, func.args.kw_defaults):
        all_args[arg.arg] = (arg, default)
    if func.args.kwarg is not None:
        all_args[func.args.kwarg.arg] = (func.args.kwarg, None)

    for name, value in decls.items():
        with markdown.list_item():
            arg, default = all_args.get(name) or (None, None)
            if arg is not None:
                content = f"**{arg.arg}**"
                if arg.annotation is not None and include_types_in_parameter_descriptions:
                    content += f" (`{ast.unparse(arg.annotation)}`)"
                if default is not None and include_defaults_in_parameter_descriptions:
                    content += f" (*Default: {ast.unparse(default)}*)"
                content += f": {value}"
                markdown.add_content(content)
            else:
                markdown.add_content(f"**{name}**: {value}")

def docstring_section_to_markdown(markdown: MarkdownWriter, node: Optional[ast.AST], section: DocstringSection) -> None:
    with markdown.title(section.name):
        with markdown.unordered_list():
            if section.name.lower() == "parameters" and isinstance(node, ast.FunctionDef):
                function_parameters_docstring_to_markdown(markdown, node, section.decls)
                return

            for name, value in section.decls.items():
                with markdown.list_item():
                    markdown.add_content(f"**{name}**: {value}")

def docstring_to_markdown(markdown: MarkdownWriter, node: ast.AST, module: Module) -> None:
    docstring = parse_numpy_docstring(node, module)
    if docstring is not None:
        if docstring.content is not None:
            markdown.add_content(docstring.content)

        for section_id in ["parameters", "returns", "raises"]:
            if section_id in docstring.sections:
                section = docstring.sections[section_id]
                docstring_section_to_markdown(markdown, node, section)

def function_to_markdown(markdown: MarkdownWriter, func: ast.FunctionDef, parent_basename: Optional[str], module: Module) -> None:
    title = "<mark style=\"color:yellow;\">def</mark> `"
    if parent_basename is not None:
        title += f"{parent_basename}."
    title += f"{func.name}()`"
    with markdown.title(title):
        function_def_to_markdown(markdown, func, parent_basename)
        docstring_to_markdown(markdown, func, module)

def class_to_markdown(markdown: MarkdownWriter, cls: ast.ClassDef, parent_basename: str, module: Module) -> None:
    with markdown.title(f"<mark style=\"color:red;\">class</mark> `{parent_basename}.{cls.name}`"):
        docstring_to_markdown(markdown, cls, module)

        # Global attributes
        attributes_to_markdown(markdown, cls.body, None, module)

        # Functions
        function_defs = [node for node in cls.body if isinstance(node, ast.FunctionDef) and not node.name.startswith("_")]
        for func in function_defs:
            function_to_markdown(markdown, func, None, module)

def extract_attributes(nodes: list[ast.stmt]) -> dict[str, tuple[ast.AST, Optional[str], Optional[str]]]:
    attrs = {}
    def _add(ass: Union[ast.Assign, ast.AnnAssign], docnode: ast.Constant):
        if isinstance(ass, ast.AnnAssign) and isinstance(ass.target, ast.Name):
            if ass.target.id.startswith("_"):
                return
            attrs[ass.target.id] = (docnode, ast.unparse(ass.annotation), ast.unparse(ass.value) if ass.value is not None else None)
        elif isinstance(ass, ast.Assign):
            for target in ass.targets:
                if not isinstance(target, ast.Name) or target.id.startswith("_"):
                    return
                attrs[target.id] = (docnode, None, ast.unparse(ass.value) if ass.value is not None else None)

    ass_node = None
    for node in nodes:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            ass_node = node
        elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str) and ass_node is not None:
            _add(ass_node, node.value)
        else:
            ass_node = None
    return attrs

def attributes_to_markdown(markdown: MarkdownWriter, nodes: list[ast.stmt], parent_basename: Optional[str], module: Module) -> None:
    attributes = extract_attributes(nodes)
    if len(attributes) > 0:
        with markdown.title("Attributes"):
            for name, (docnode, annotation, value) in attributes.items():
                attr_name = name if parent_basename is None else f"{parent_basename}.{name}"
                with markdown.title(f"<mark style=\"color:yellow;\">attr</mark> `{attr_name}`"):
                    markdown.add_line("```python")
                    repr = f"{attr_name}"
                    if annotation is not None:
                        repr += f": {annotation}"
                    if value is not None:
                        repr += f" = {value}"
                    markdown.add_line(repr)
                    markdown.add_line("```")
                    docstring_to_markdown(markdown, docnode, module)

def module_to_markdown(markdown: MarkdownWriter, module: Module) -> None:
    with markdown.title(module.name):
        module_doc = module.docstring
        if module_doc is not None:
            markdown.add_content(module_doc)

        # Subpackages
        if len(module.packages) > 0:
            with markdown.title("Subpackages"):
                with markdown.unordered_list():
                    for submod in module.packages:
                        with markdown.list_item():
                            submod_ref = astdown.loader.replace_crossrefs(f"`{module.basename}.{submod.basename}`", submod.ast, submod)
                            markdown.add_content(f"{submod_ref} ‒ {short_docstring(submod.ast, submod) or '*No description.*'}")

        # Submodules
        if len(module.modules) > 0:
            with markdown.title("Submodules"):
                with markdown.unordered_list():
                    for submod in module.modules:
                        with markdown.list_item():
                            submod_ref = astdown.loader.replace_crossrefs(f"`{module.basename}.{submod.basename}`", submod.ast, submod)
                            markdown.add_content(f"{submod_ref} ‒ {short_docstring(submod.ast, submod) or '*No description.*'}")

        # Global attributes
        attributes_to_markdown(markdown, module.ast.body, module.basename, module)

        # Classes
        class_defs = [node for node in module.ast.body if isinstance(node, ast.ClassDef) and not node.name.startswith("_")]
        for cls in class_defs:
            class_to_markdown(markdown, cls, module.basename, module)

        # Functions
        function_defs = [node for node in module.ast.body if isinstance(node, ast.FunctionDef) and not node.name.startswith("_")]
        for func in function_defs:
            function_to_markdown(markdown, func, module.basename, module)
