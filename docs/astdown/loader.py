from __future__ import annotations
import ast
import os
import sys
from ast import Module as AstModule
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional

@dataclass
class IndexEntry:
    type: Literal["module", "function", "attribute", "class"]
    fqname: str
    name: str
    parent: Optional[IndexEntry]
    module: Optional[IndexEntry]
    module_url: Optional[str]
    node: ast.AST

    def short_name(self):
        return '.'.join(self.fqname.split(".")[-2:])

    def display_name(self):
        dn = self.short_name()
        if self.type == "function":
            dn += "()"
        return dn

    def url(self, relative_to: Optional[str] = None):
        if self.type == "module":
            subref = ""
        elif self.type == "function":
            subref = f"#def-{self.short_name()}"
        elif self.type == "class":
            subref = f"#class-{self.short_name()}"
        elif self.type == "attribute":
            subref = f"#attr-{self.short_name()}"
        else:
            raise ValueError(f"Invalid {self.type=}")

        module = self.module or self
        relative_path = module.module_url or ""
        if relative_to is not None:
            relative_path = os.path.relpath(relative_path, start=os.path.dirname(relative_to))
        return relative_path + subref

def replace_crossrefs(content: str, node: ast.AST, module: Module) -> str:
    """Currently intended to be monkeypatched."""
    _ = (node, module)
    return content

def docstring(node: ast.AST, module: Module) -> Optional[str]:
    docstr = ast.get_docstring(node)
    if docstr is None:
        return None
    return replace_crossrefs(docstr, node, module)

def short_docstring(node: ast.AST, module: Module) -> Optional[str]:
    content = docstring(node, module)
    if content is None or content == "":
        return None
    locs = [len(content) - 1, content.find(". "), content.find(".\n"), content.find("\n\n")]
    first_dot_or_paragraph_end = min(l for l in locs if l > 0)
    return content[:first_dot_or_paragraph_end + 1]

@dataclass
class Module:
    name: str
    path: str
    modules: list[Module] = field(default_factory=list)
    packages: list[Module] = field(default_factory=list)
    index: Optional[dict[str, IndexEntry]] = None
    _ast: Optional[AstModule] = None

    @property
    def basename(self) -> str:
        return self.name.split('.')[-1]

    @property
    def ast(self) -> AstModule:
        if self._ast is None:
            with open(self.path, "r") as f:
                self._ast = ast.parse(f.read(), filename=self.path)
        return self._ast

    @property
    def docstring(self) -> Optional[str]:
        return docstring(self.ast, self)

    def generate_index(self, url: str) -> None:
        index: dict[str, IndexEntry] = {}
        index[self.name] = module_index = IndexEntry("module", self.name, self.name, None, None, url, self.ast)

        def _fqname(parent: IndexEntry, name: str):
            return f"{parent.fqname}.{name}"

        def _index_functions(body: list[ast.stmt], parent: IndexEntry):
            for node in body:
                # Functions
                if isinstance(node, ast.FunctionDef):
                    fqname = _fqname(parent, node.name)
                    index[fqname] = IndexEntry("function", fqname, node.name, parent, module_index, None, node)

        def _index_attributes(body: list[ast.stmt], parent: IndexEntry):
            for node in body:
                # Attributes
                if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                    fqname = _fqname(parent, node.target.id)
                    index[fqname] = IndexEntry("attribute", fqname, node.target.id, parent, module_index, None, node)
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            fqname = _fqname(parent, target.id)
                            index[fqname] = IndexEntry("attribute", fqname, target.id, parent, module_index, None, node)

        def _index_classes(body: list[ast.stmt], parent: IndexEntry):
            for node in body:
                if isinstance(node, ast.ClassDef):
                    fqname = _fqname(parent, node.name)
                    index[fqname] = class_index = IndexEntry("class", fqname, node.name, parent, module_index, None, node)
                    _index_functions(node.body, class_index)
                    _index_attributes(node.body, class_index)
                    _index_classes(node.body, class_index)

        _index_functions(self.ast.body, module_index)
        _index_attributes(self.ast.body, module_index)
        _index_classes(self.ast.body, module_index)

        self.index = index

def find_module(module_name: str) -> Optional[str]:
    parts = module_name.split('.')
    filenames = [os.path.join(*parts, '__init__.py'),
                 os.path.join(*parts) + '.py']

    for path in sys.path:
        for choice in filenames:
            abs_path = os.path.normpath(os.path.join(path, choice))
            if os.path.isfile(abs_path):
                return abs_path

def _package_module_recursive(package_name: str, package_dir: Path) -> Optional[Module]:
    module_path = package_dir / "__init__.py"
    if not module_path.is_file():
        return None

    module = Module(name=package_name, path=str(module_path))
    for x in package_dir.iterdir():
        if x.is_dir() and (x / "__init__.py").is_file():
            sub_package = _package_module_recursive(f"{package_name}.{x.name}", x)
            if sub_package is not None:
                module.packages.append(sub_package)
        elif x.is_file() and x.name.endswith(".py") and x.name != "__init__.py":
            module.modules.append(Module(name=f"{package_name}.{x.name[:-len('.py')]}", path=str(x)))
    return module

def find_package_or_module(package_name: str) -> Optional[Module]:
    module_path = find_module(package_name)
    if module_path is None:
        return None
    if module_path.endswith("__init__.py"):
        return _package_module_recursive(package_name, Path(module_path).parent)
    return Module(name=package_name, path=module_path)
