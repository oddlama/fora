#!/usr/bin/env python3

import argparse
import ast
import os
import shutil
import sys
from itertools import zip_longest
from pathlib import Path
from typing import Optional
from rich import print
from rich.markdown import Markdown
from textwrap import dedent

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

def function_signature(func: ast.FunctionDef, module_source: str, module_basename: str, max_width: int = max_function_signature_width) -> str:
    if len(func.args.posonlyargs) > 0:
        raise NotImplementedError(f"functions with 'posonlyargs' are not supported.")

    # Word tokens that need to be joined together, but should be wrapped
    # before overflowing to the right.
    tokens = [f"def {module_basename}.{func.name}("]
    indent_width = len(tokens[0])

    def _arg_to_str(arg: ast.arg, default: Optional[ast.expr] = None, prefix: str = ""):
        include_annotation = arg.annotation is not None and False # TODO
        arg_token = prefix + arg.arg
        if include_annotation:
            arg_token += f": {ast.get_source_segment(module_source, arg.annotation) or ''}"
        if default is not None:
            arg_token += " = " if include_annotation else "="
            arg_token += ast.get_source_segment(module_source, default) or ""
        return arg_token

    arg: ast.arg
    default: Optional[ast.expr]
    args = []
    for arg, default in reversed(list(zip_longest(reversed(func.args.args), reversed(func.args.defaults)))):
        args.append(_arg_to_str(arg, default))
    if func.args.vararg is not None:
        args.append(_arg_to_str(func.args.vararg, prefix="*"))

    for arg, default in zip(func.args.kwonlyargs, func.args.kw_defaults):
        args.append(_arg_to_str(arg, default))
    if func.args.kwarg is not None:
        args.append(_arg_to_str(func.args.kwarg, prefix="**"))

    # Append commatas to arguments followed by arguments.
    for a in args[:-1]:
        a += ","
    tokens.extend(args)
    tokens.append("):")

    markdown = "```python\n"
    markdown += '\n'.join(tokens)
    markdown += "```\n"
    return markdown

def generate_module_documentation(module_name: str, build_path: Path) -> None:
    # Find module path
    module_path = find_module(module_name)
    with open(module_path, "r") as f:
        module_source = f.read()

    # Load module ast
    module_ast = ast.parse(module_source, filename=module_path)
    function_defs = [node for node in module_ast.body if isinstance(node, ast.FunctionDef)]

    markdown = f"# {module_name}\n\n"
    module_basename = module_name.split(".")[-1]

    for func in function_defs:
        if func.name.startswith("_"):
            continue

        docstring = ast.get_docstring(func)
        print(func.__dict__, docstring)

        markdown += f"## {module_basename}.{func.name}\n\n"
        markdown += function_signature(func, module_source, module_basename) + "\n"

    print(Markdown(markdown))
    print("------------")
    print(markdown)

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
    generate_module_documentation("fora.operations.files", build_path)

if __name__ == "__main__":
    main()
