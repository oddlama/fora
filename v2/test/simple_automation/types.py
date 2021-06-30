"""
Provides a mockup of types for the static type checker so it
has a better understanding of the dynamically loaded modules.
"""

from types import ModuleType
from typing import Union

class GroupType(ModuleType):
    """
    A mockup type for group modules. This is not the actual type of an instanciated
    module, but will reflect some of it's properties better than ModuleType.
    """

    _name: str = ''
    """
    The name of this module. Determined by the filename in which it is stored.
    """

    _after: list[str] = []
    """
    A list of groups that must be applied after this group has been applied.
    """

    _before: list[str] = []
    """
    A list of groups that must be applied before this group has been applied.
    """

    _loaded_from: str
    """
    A string containing the path from which this module has been loaded.
    """

class HostType(ModuleType):
    """
    A mockup type for host modules. This is not the actual type of an instanciated
    module, but will reflect some of it's properties better than ModuleType.
    """

class InventoryType(ModuleType):
    """
    A mockup type for inventory modules. This is not the actual type of an instanciated
    module, but will reflect some of it's properties better than ModuleType.
    """

    hosts: list[Union[str, tuple[str, str]]] = []
    """
    The list of hosts that belong to this inventory and have to be loaded.
    """

class TaskType(ModuleType):
    """
    A mockup type for task modules. This is not the actual type of an instanciated
    module, but will reflect some of it's properties better than ModuleType.
    """

    _name: str = ''
    """
    The name of this module. Determined by the filename in which it is stored.
    """
