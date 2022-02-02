from __future__ import annotations
import ast
import os
import sys
from ast import Module as AstModule
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional

IndexType = tuple[Literal["module", "function", "attribute", "class", "class_function", "class_attribute"], str, str, ast.AST]

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
    docstr = ast.get_docstring(node)
    if docstr is None:
        return None
    content = replace_crossrefs(docstr, node, module)
    first_dot_or_paragraph_end = min(content.find(". "), content.find(".\n"), content.find("\n\n"))
    return content[:first_dot_or_paragraph_end + 1]

@dataclass
class Module:
    name: str
    path: str
    modules: list[Module] = field(default_factory=list)
    packages: list[Module] = field(default_factory=list)
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

    def index(self) -> dict[str, IndexType]:
        index: dict[str, IndexType] = {}
        index[self.name] = ("module", self.name, "", self.ast)

        for node in self.ast.body:
            # Classes
            if isinstance(node, ast.ClassDef):
                index[f"{self.name}.{node.name}"] = ("class", self.name, node.name, node)

                for class_node in node.body:
                    # Functions
                    if isinstance(class_node, ast.FunctionDef):
                        index[f"{self.name}.{node.name}.{class_node.name}"] = ("class_function", self.name, f"{node.name}.{class_node.name}", class_node)

                    # Attributes
                    if isinstance(class_node, ast.AnnAssign) and isinstance(class_node.target, ast.Name):
                        index[f"{self.name}.{node.name}.{class_node.target.id}"] = ("class_attribute", self.name, f"{node.name}.{class_node.target.id}", class_node)
                    if isinstance(class_node, ast.Assign):
                        for target in class_node.targets:
                            if isinstance(target, ast.Name):
                                index[f"{self.name}.{node.name}.{target.id}"] = ("class_attribute", self.name, f"{node.name}.{target.id}", class_node)

            # Functions
            if isinstance(node, ast.FunctionDef):
                index[f"{self.name}.{node.name}"] = ("function", self.name, node.name, node)

            # Attributes
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                index[f"{self.name}.{node.target.id}"] = ("attribute", self.name, node.target.id, node)
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        index[f"{self.name}.{target.id}"] = ("attribute", self.name, target.id, node)

        return index

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
