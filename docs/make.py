#!/usr/bin/env python3

import argparse
import shutil
import sys
from pathlib import Path
from typing import Any
from rich import print as rprint
from rich.markup import escape as rescape

from astdown.loader import load_module_ast
from astdown.markdown import MarkdownWriter, module_to_markdown

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

    # Add args to python module search path
    for p in args.include_path:
        sys.path.insert(0, p)

    # Recursively find all relevant modules
    # TODO

    # Generate documentation
    markdown = MarkdownWriter()
    module = load_module_ast("fora.operations.files")
    module_to_markdown(markdown, module)

    print(markdown.content.strip())

if __name__ == "__main__":
    main()
