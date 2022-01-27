import ast
from dataclasses import dataclass, field
from itertools import zip_longest
from typing import Any, Callable, ContextManager, Optional

from astdown.docstring import DocstringSection, parse_numpy_docstring
from astdown.loader import ModuleAst

include_annotations_in_signature = True
include_annotations_in_parameter_descriptions = False
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

    def unordered_list(self) -> ContextManager:
        def _enter():
            self.margin(1)
            self.lists.append("-")
        def _exit():
            self.margin(1)
            self.lists.pop()
        return _DelegateContextManager(_enter, _exit)

    def list_item(self) -> ContextManager:
        def _enter():
            self.indents.append("    ")
            self._calculate_indent()
            self.needs_bullet_point = True
        def _exit():
            self.indents.pop()
            self._calculate_indent()
            if self.needs_bullet_point:
                self.add_line("")
                self.needs_bullet_point = False
        return _DelegateContextManager(_enter, _exit)

def function_def_to_markdown(markdown: MarkdownWriter, func: ast.FunctionDef, module: ModuleAst) -> None:
    if len(func.args.posonlyargs) > 0:
        raise NotImplementedError(f"functions with 'posonlyargs' are not supported.")

    # Word tokens that need to be joined together, but should be wrapped
    # before overflowing to the right. If the required alignment width
    # becomes too high, we fall back to simple fixed alignment.
    initial_str = f"def {module.basename}.{func.name}("
    align_width = len(initial_str)
    if align_width > 32:
        align_width = 8

    def _arg_to_str(arg: ast.arg, default: Optional[ast.expr] = None, prefix: str = ""):
        arg_token = prefix + arg.arg
        equals_separator = "="
        if arg.annotation is not None and include_annotations_in_signature:
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
    tokens.append("):")

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
                if arg.annotation is not None and include_annotations_in_parameter_descriptions:
                    content += f" (`{ast.unparse(arg.annotation)}`)"
                if default is not None and include_defaults_in_parameter_descriptions:
                    content += f" (*Default: {ast.unparse(default)}*)"
                content += f": {value}"
                markdown.add_content(content)
            else:
                markdown.add_content(f"**{name}**: {value}")

def function_docstring_section_to_markdown(markdown: MarkdownWriter, func: ast.FunctionDef, section: DocstringSection) -> None:
    with markdown.title(section.name):
        with markdown.unordered_list():
            if section.name.lower() == "parameters":
                function_parameters_docstring_to_markdown(markdown, func, section.decls)
                return

            for name, value in section.decls.items():
                with markdown.list_item():
                    markdown.add_content(f"**{name}**: {value}")

def function_docstring_to_markdown(markdown: MarkdownWriter, func: ast.FunctionDef, module: ModuleAst) -> None:
    docstring = parse_numpy_docstring(func, module)
    if docstring is not None:
        if docstring.content is not None:
            markdown.add_content(docstring.content)

        for section_id in ["parameters", "returns", "raises"]:
            if section_id in docstring.sections:
                section = docstring.sections[section_id]
                function_docstring_section_to_markdown(markdown, func, section)

def function_to_markdown(markdown: MarkdownWriter, func: ast.FunctionDef, module: ModuleAst) -> None:
    function_def_to_markdown(markdown, func, module)
    function_docstring_to_markdown(markdown, func, module)

def class_to_markdown(markdown: MarkdownWriter, cls: ast.ClassDef, module: ModuleAst) -> None:
    pass

def module_to_markdown(markdown: MarkdownWriter, module: ModuleAst) -> None:
    with markdown.title(module.name):
        # Submodules

        # Classes
        class_defs = [node for node in module.ast.body if isinstance(node, ast.ClassDef) and not node.name.startswith("_")]
        for cls in class_defs:
            with markdown.title(f"class {module.basename}.{cls.name}"):
                class_to_markdown(markdown, cls, module)

        # Functions
        function_defs = [node for node in module.ast.body if isinstance(node, ast.FunctionDef) and not node.name.startswith("_")]
        for func in function_defs:
            with markdown.title(f"{module.basename}.{func.name}()"):
                function_to_markdown(markdown, func, module)
