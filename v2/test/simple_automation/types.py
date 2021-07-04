"""
Provides a mockup of types for the static type checker so it
has a better understanding of the dynamically loaded modules.
"""

from types import ModuleType
from typing import cast, Union

from .host import HostMeta
from .group import GroupMeta

class GroupType(ModuleType):
    """
    A mockup type for group modules. This is not the actual type of an instanciated
    module, but will reflect some of it's properties better than ModuleType.
    """

    reserved_vars: set[str] = set(["meta"])
    """
    A list of variable names that are reserved and must not be set by the module.
    """

    meta: GroupMeta = cast(GroupMeta, None)

class HostType(ModuleType):
    """
    A mockup type for host modules. This is not the actual type of an instanciated
    module, but will reflect some of it's properties better than ModuleType.
    """

    reserved_vars: set[str] = set(["meta"])
    """
    A list of variable names that are reserved and must not be set by the module.
    """

    meta: HostMeta = cast(HostMeta, None)

class InventoryType(ModuleType):
    """
    A mockup type for inventory modules. This is not the actual type of an instanciated
    module, but will reflect some of it's properties better than ModuleType.
    """

    hosts: list[Union[str, tuple[str, str]]] = []
    """
    The list of hosts that belong to this inventory and have to be loaded.
    """
