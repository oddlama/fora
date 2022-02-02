#!/usr/bin/env python3

import argparse
import ast
import functools
import re
import shutil
import sys
from pathlib import Path
from textwrap import dedent
from typing import Any, Optional, Union

import astdown.loader
from astdown.loader import Module, find_package_or_module, short_docstring
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
    ### parser.add_argument('modules', nargs='+', type=str,
    ###         help="The modules to generate documentation for.")
    args = parser.parse_args()

    # TODO this is only for fora. make the tool generic at some point
    args.modules = ["fora"]
    ref_prefix = "api/"

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

    def _to_path(module: Module) -> str:
        #if len(module.modules) > 0 or len(module.packages) > 0:
        #    return f"{module.name.replace('.', '/')}/__init__.md"
        #else:
        return f"{module.name.replace('.', '/')}.md"

    # Index references
    print("Indexing references")
    index = {}
    for module in modules.values():
        module.generate_index(ref_prefix + _to_path(module))
        index.update(module.index or {})

    # Register cross-reference replacer
    def _replace_crossref(match: Any, node: ast.AST, module: Module) -> str:
        fqname = match.group(1)
        if fqname.startswith(".") or fqname.endswith("."):
            return match.group(0)
        if fqname not in index and "." in fqname:
            for key in index:
                if key.endswith(fqname):
                    fqname = key
                    break
        if fqname not in index:
            if "." in fqname:
                print(f"warning: Skipping invalid reference '{match.group(1)}' in {module.path}:{node.lineno}", file=sys.stderr)
            return match.group(0)

        idx = index[fqname]
        module_idx = index[module.name]
        url = idx.url(relative_to=module_idx.url()).replace('_', r'\_')
        return f"[`{idx.display_name()}`]({url})"

    ref_pattern = re.compile(r"(?<!\[)`([a-zA-Z_0-9.]*)`")
    def _replace_crossrefs(content: str, node: ast.AST, module: Module) -> str:
        return ref_pattern.sub(functools.partial(_replace_crossref, node=node, module=module), content)
    astdown.loader.replace_crossrefs = _replace_crossrefs

    def _link_to(fqname: str, display_name: Optional[str] = None, relative_to: Optional[Union[Module, str]] = None, code: bool = True) -> str:
        idx = index[fqname]
        to = None
        if relative_to is not None:
            to = relative_to.name if isinstance(relative_to, Module) else relative_to
        if display_name is None:
            display_name = idx.display_name()
        assert display_name is not None
        if not code:
            display_name = display_name.replace('_', r'\_')
        url = idx.url(to).replace('_', r'\_')
        cm = "`" if code else ""
        return f"[{cm}{display_name}{cm}]({url})"

    # Generate documentation
    print("Generating markdown")
    for i,module in enumerate(modules.values()):
        print(f"[{100*(i+1)/len(modules):6.2f}%] Processing {module.name}")
        markdown = MarkdownWriter()
        module_to_markdown(markdown, module)
        file_path = build_path / _to_path(module)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w") as f:
            f.write(markdown.content.strip("\n") + "\n")

    # Generate API index
    print("Generating API index")
    markdown = MarkdownWriter()
    name_overrides = {"fora": "Fora API"}
    def _recursive_list_module(module: Module):
        with markdown.list_item(indent="  "):
            markdown.add_line(_link_to(module.name, display_name=name_overrides.get(module.name), code=False))
            if len(module.modules) > 0:
                with markdown.unordered_list(sign="*"):
                    for submod in sorted(module.packages, key=lambda x: x.name):
                        _recursive_list_module(submod)
                    for submod in sorted(module.modules, key=lambda x: x.name):
                        with markdown.list_item(indent="  "):
                            markdown.add_line(_link_to(submod.name, code=False))

    with markdown.title("Fora API"):
        markdown.margin(2)
        with markdown.unordered_list(sign="*"):
            with markdown.list_item(indent="  "):
                markdown.add_line(r"[Operations Index](api/index\_operations.md)")
            _recursive_list_module(modules["fora"])

    with open(build_path / f"API_SUMMARY.md", "w") as f:
        f.write(dedent(
            markdown.content
                .replace("*  ", "* ")
                .strip("\n")
                .replace("\n\n", "\n")) + "\n")

    # Generate Operations index
    print("Generating operations index")
    markdown = MarkdownWriter()
    with markdown.title("Operations"):
        for submod in sorted(modules["fora.operations"].modules, key=lambda x: x.name):
            if submod.name in ["fora.operations.api", "fora.operations.utils"]:
                continue
            with markdown.title(index[submod.name].display_name()):
                assert submod.index is not None
                for key, idx in submod.index.items():
                    if "._" in key:
                        continue
                    if idx.type != "function":
                        continue
                    with markdown.unordered_list():
                        with markdown.list_item():
                            markdown.add_content(_link_to(key, relative_to=ref_prefix) + f" ‒ {short_docstring(idx.node, submod)}")

    with open(build_path / f"index_operations.md", "w") as f:
        f.write(markdown.content.strip("\n") + "\n")

if __name__ == "__main__":
    main()
