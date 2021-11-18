#!/usr/bin/env python3

from pathlib import Path
import pdoc
import pdoc.render
import shutil

docs = Path(__file__).parent
root = docs / ".."

if __name__ == "__main__":
    build = docs / "build"
    if build.exists():
        shutil.rmtree(build)

    # Render main docs
    pdoc.render.configure(docformat='numpy', template_directory=docs / "pdoc-theme-bulma")
    pdoc.pdoc(root / "simple_automation", output_directory=build)
