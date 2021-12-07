"""This package contains all standard operation modules."""

import importlib
import pkgutil
from types import ModuleType
from typing import Union

def _import_submodules(package: Union[str, ModuleType], recursive: bool = False) -> dict[str, ModuleType]:
    """
    Import all submodules of a module, possibly recursively including subpackages.

    Parameters
    ----------
    package
        The package to import all submodules from.
    recursive
        Whether to recursively include subpackages.

    Returns
    -------
    dict[str, ModuleType]
    """
    if isinstance(package, str):
        package = importlib.import_module(package)
    results = {}
    for _, name, is_pkg in pkgutil.walk_packages(package.__path__): # type: ignore[attr-defined]
        full_name = package.__name__ + '.' + name
        results[full_name] = importlib.import_module(full_name)
        if recursive and is_pkg:
            results.update(_import_submodules(results[full_name]))
    return results

# Import all submodules to ensure that decorators have a chance
# to register operations to a registry (e.g. package_managers).
__all__: list[str] = []
_import_submodules(__name__)
