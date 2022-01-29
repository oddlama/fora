#!/usr/bin/env python3

import argparse
import shutil
import sys
from pathlib import Path
from typing import Any

from astdown.loader import Module, find_package_or_module
from astdown.markdown import MarkdownWriter, module_to_markdown

from rich import print as rprint
from rich.markup import escape as rescape
def print(msg: Any, *args, **kwargs):
    rprint(rescape(msg) if isinstance(msg, str) else msg, *args, **kwargs)

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
    build_path.mkdir(parents=True, exist_ok=True)

    # Add args to python module search path
    for p in args.include_path:
        sys.path.insert(0, p)

    # Find packages and modules
    stack: list[Module] = []
    for i in args.modules:
        module = find_package_or_module(i)
        if module is None:
            raise ModuleNotFoundError(f"Could not find source file for module '{i}'")
        stack.append(module)

    # Deduplicate and flatten
    modules: dict[str, Module] = {}
    while len(stack) > 0:
        m = stack.pop()
        if m.name in modules:
            continue
        modules[m.name] = m
        stack.extend(m.packages)
        stack.extend(m.modules)

    # Generate documentation
    for i,module in enumerate(modules.values()):
        print(f"[{100*(i+1)/len(modules):6.2f}%] processing {module.name}")
        markdown = MarkdownWriter()
        module_to_markdown(markdown, module)
        with open(build_path / f"{module.name}.md", "w") as f:
            f.write(markdown.content.strip())

if __name__ == "__main__":
    main()
