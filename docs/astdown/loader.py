from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import ast as stdlib_ast
import os
import sys

@dataclass
class Module:
    name: str
    path: str
    modules: list[Module] = field(default_factory=list)
    packages: list[Module] = field(default_factory=list)
    _ast: Optional[stdlib_ast.Module] = None

    @property
    def basename(self) -> str:
        return self.name.split('.')[-1]

    @property
    def ast(self) -> stdlib_ast.Module:
        if self._ast is None:
            with open(self.path, "r") as f:
                self._ast = stdlib_ast.parse(f.read(), filename=self.path)
        return self._ast

    @property
    def docstring(self) -> Optional[str]:
        return stdlib_ast.get_docstring(self.ast)

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
