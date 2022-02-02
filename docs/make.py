#!/usr/bin/env python3

import argparse
import ast
import functools
import re
import shutil
import sys
from pathlib import Path
from typing import Any

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

    # Index references
    print("Indexing references")
    index = {}
    for module in modules.values():
        index.update(module.index())

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
        _, mod_name, node_name, node = index[fqname]
        subref = f"#{node_name}" if node_name else ""
        short_name = f"{mod_name}.{node_name}" if node_name else mod_name
        short_name = '.'.join(short_name.split(".")[-2:])
        if isinstance(node, ast.FunctionDef):
            short_name += "()"
        mod = modules[mod_name]
        if len(mod.modules) > 0 or len(mod.packages) > 0:
            ref_path = f"{mod_name.replace('.', '/')}/__init__.md"
        else:
            ref_path = f"{mod_name.replace('.', '/')}.md"
        ref = ref_prefix + ref_path + subref
        ref = ref.replace("_", r"\_")
        return f"[`{short_name}`]({ref})"

    ref_pattern = re.compile(r"(?<!\[)`([a-zA-Z_0-9.]*)`")
    def _replace_crossrefs(content: str, node: ast.AST, module: Module) -> str:
        return ref_pattern.sub(functools.partial(_replace_crossref, node=node, module=module), content)
    astdown.loader.replace_crossrefs = _replace_crossrefs

    # Generate documentation
    print("Generating markdown")
    for i,module in enumerate(modules.values()):
        print(f"[{100*(i+1)/len(modules):6.2f}%] Processing {module.name}")
        markdown = MarkdownWriter()
        module_to_markdown(markdown, module)
        if len(module.modules) > 0 or len(module.packages) > 0:
            file_path = build_path / f"{module.name.replace('.', '/')}/__init__.md"
        else:
            file_path = build_path / f"{module.name.replace('.', '/')}.md"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w") as f:
            f.write(markdown.content.strip("\n") + "\n")

    # Generate API index
    print("Generating API index")
    markdown = MarkdownWriter()
    def _recursive_list_module(module: Module):
        with markdown.list_item(indent="  "):
            markdown.add_line(_replace_crossrefs(f"`{module.name}`", module.ast, module).replace("[`", "[").replace("`]", "]"))
            if len(module.modules) > 0:
                with markdown.unordered_list(sign="*"):
                    for submod in sorted(module.packages, key=lambda x: x.name):
                        _recursive_list_module(submod)
                    for submod in sorted(module.modules, key=lambda x: x.name):
                        with markdown.list_item(indent="  "):
                            markdown.add_line(_replace_crossrefs(f"`{submod.name}`", submod.ast, submod).replace("[`", "[").replace("`]", "]"))

    with markdown.unordered_list(sign="*"):
        _recursive_list_module(modules["fora"])

    with open(build_path / f"API_SUMMARY.md", "w") as f:
        f.write(markdown.content.strip("\n").replace("\n\n", "\n") + "\n")

    # Generate Operations index
    print("Generating operations index")
    markdown = MarkdownWriter()
    with markdown.title("Operations"):
        for submod in sorted(modules["fora.operations"].modules, key=lambda x: x.name):
            if submod.name in ["fora.operations.api", "fora.operations.utils"]:
                continue
            with markdown.title(_replace_crossrefs(f"`{submod.name}`", submod.ast, submod)):
                for key, (type, mod_name, _, node) in index.items():
                    if "._" in key:
                        continue
                    if not mod_name == submod.name or type != "function":
                        continue
                    with markdown.unordered_list():
                        with markdown.list_item():
                            markdown.add_content(_replace_crossrefs(f"`{key}`", node, submod) + f" ‒ {short_docstring(node, submod)}")

    with open(build_path / f"index_operations.md", "w") as f:
        f.write(markdown.content.strip("\n") + "\n")

if __name__ == "__main__":
    main()
