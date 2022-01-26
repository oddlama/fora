#!/usr/bin/env python3

import argparse
import ast
from dataclasses import dataclass, field
import os
import shutil
import sys
from itertools import zip_longest
from pathlib import Path
from typing import Any, Callable, ContextManager, Optional, cast
from rich import print
from rich.markdown import Markdown
from textwrap import dedent

markdown_wrap = 120
max_function_signature_width = 76

def find_module(module_name: str) -> str:
    parts = module_name.split('.')
    filenames = [os.path.join(*parts, '__init__.py'),
                 os.path.join(*parts) + '.py']

    for path in sys.path:
        for choice in filenames:
            abs_path = os.path.normpath(os.path.join(path, choice))
            if os.path.isfile(abs_path):
                return abs_path

    raise ModuleNotFoundError(f"Could not find source file for module '{module_name}'")

@dataclass
class DocModule:
    path: str
    name: str
    basename: str
    source: str
    ast: ast.Module

@dataclass
class DelegateContextManager:
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
    indents: list = field(default_factory=list)
    indent_str: str = ""

    def _calculate_indent(self):
        self.indent_str = ''.join(self.indents)

    def margin(self, newlines: int):
        existing_newlines = 0
        for c in reversed(self.content):
            if c != "\n":
                break
            existing_newlines += 1
        self.content += max(newlines - existing_newlines, 0) * "\n"

    def add_line(self, line: str):
        self.content += self.indent_str + line
        if not line.endswith("\n"):
            self.content += "\n"

    def add_content(self, text: str):
        # TODO merge lines, except double newlines, resplit at 120 characters
        self.content += self.indent_str + text

    def title(self, title: str) -> ContextManager:
        def _enter():
            self.title_depth += 1
            self.add_line("#" * self.title_depth + " " + title)
            self.margin(2)
        def _exit():
            self.title_depth -= 1
        return DelegateContextManager(_enter, _exit)

def function_def_to_markdown(markdown: MarkdownWriter, func: ast.FunctionDef, module: DocModule, max_width: int = max_function_signature_width) -> None:
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
        include_annotation = arg.annotation is not None and False # TODO
        arg_token = prefix + arg.arg
        if include_annotation:
            arg_token += f": {ast.get_source_segment(module.source, cast(ast.expr, arg.annotation)) or ''}"
        if default is not None:
            arg_token += " = " if include_annotation else "="
            arg_token += ast.get_source_segment(module.source, default) or ""
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

    # Append commatas to arguments followed by arguments.
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
        if len(line) + len(t.rstrip()) > max_width:
            _commit()

        if line == "":
            line += align_width * " "
        line += t

    _commit()
    markdown.add_line("```")

def function_docstring_to_markdown(markdown: MarkdownWriter, func: ast.FunctionDef, module: DocModule) -> None:
    docstring = ast.get_docstring(func)
    if docstring is not None:
        markdown.add_content(docstring)
        markdown.margin(2)

def function_to_markdown(markdown: MarkdownWriter, func: ast.FunctionDef, module: DocModule) -> None:
    function_def_to_markdown(markdown, func, module)
    function_docstring_to_markdown(markdown, func, module)

def load_module_ast(module_name: str) -> DocModule:
    # Find module path
    module_path = find_module(module_name)
    with open(module_path, "r") as f:
        module_source = f.read()

    # Load module ast
    module_ast = ast.parse(module_source, filename=module_path, type_comments=True)
    return DocModule(path=module_path, name=module_name, basename=module_name.split(".")[-1],
                     source=module_source, ast=module_ast)

def module_to_markdown(markdown: MarkdownWriter, module: DocModule) -> None:
    with markdown.title(module.name):
        function_defs = [node for node in module.ast.body if isinstance(node, ast.FunctionDef)]
        for func in function_defs:
            if func.name.startswith("_"):
                continue

            with markdown.title(f"{module.basename}.{func.name}"):
                function_to_markdown(markdown, func, module)

def main():
    parser = argparse.ArgumentParser(description="Builds the documentation for fora.")
    parser.add_argument('-o', '--output-dir', dest='output_dir', default="build", type=str,
            help="Specifies the output directory for the documentation. (default: 'build')")
    parser.add_argument('-I', '--include-path', dest='include_path', action='append', default=[], type=str,
            help="Specify an additional directory to add to the python module search path. Can be given multiple times.")
    parser.add_argument('--clean', action='store_true',
            help="Clean the build directory before generating new documentation.")
    parser.add_argument('modules', nargs='+', type=str,
            help="The modules to generate documentation for.")
    args = parser.parse_args()

    build_path = Path(args.output_dir)

    if args.clean:
        # Clean last build
        if build_path.exists():
            shutil.rmtree(build_path)

    # Add args to python module search path
    for p in args.include_path:
        sys.path.insert(0, p)

    # Load all relevant modules
    # TODO

    # Generate documentation
    markdown = MarkdownWriter()
    module = load_module_ast("fora.operations.files")
    module_to_markdown(markdown, module)

    print(Markdown(markdown.content))
    print("------------")
    print(markdown.content)

if __name__ == "__main__":
    main()
