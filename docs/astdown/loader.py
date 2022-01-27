import ast
from dataclasses import dataclass
import os
import sys

@dataclass
class ModuleAst:
    path: str
    name: str
    basename: str
    source: str
    ast: ast.Module

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

def load_module_ast(module_name: str) -> ModuleAst:
    # Find module path
    module_path = find_module(module_name)
    with open(module_path, "r") as f:
        module_source = f.read()

    # Load module ast
    module_ast = ast.parse(module_source, filename=module_path)
    return ModuleAst(path=module_path, name=module_name, basename=module_name.split(".")[-1],
                     source=module_source, ast=module_ast)
