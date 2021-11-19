#!/usr/bin/env python3

from pathlib import Path
import argparse
import pdoc
import pdoc.render
import shutil

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Builds the documentation for fora.")
    parser.add_argument('-o', '--output-dir', dest='output', default="build", type=str,
            help="Specifies the output directory for the documentation. (default: 'build')")
    args: argparse.Namespace = parser.parse_args()

    docs = Path(__file__).parent
    root = docs / ".."

    # Clean last build
    build = docs / args.output
    if build.exists():
        shutil.rmtree(build)

    # Render main docs
    pdoc.render.configure(docformat='numpy', template_directory=docs / "pdoc-theme-bulma")
    pdoc.pdoc(root / "src" / "fora", output_directory=build)
