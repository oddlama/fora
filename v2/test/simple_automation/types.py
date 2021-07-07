"""
Provides a mockup of types for the static type checker so it
has a better understanding of the dynamically loaded modules.
"""

from __future__ import annotations

from types import ModuleType
from typing import cast, Union, TYPE_CHECKING

if TYPE_CHECKING:
    # pylint: disable=cyclic-import
    # Related to bug in pylint (https://github.com/PyCQA/pylint/issues/3525)
    from .host import HostMeta
    from .group import GroupMeta
    from .task import TaskMeta

class GroupType(ModuleType):
    """
    A mockup type for group modules. This is not the actual type of an instanciated
    module, but will reflect some of it's properties better than ModuleType.
    """

    reserved_vars: set[str] = set(["meta"])
    """
    A list of variable names that are reserved and must not be set by the module.
    """

    def __init__(self):
        self.meta: GroupMeta = cast('GroupMeta', None)
        """
        The associated meta information
        """

class HostType(ModuleType):
    """
    A mockup type for host modules. This is not the actual type of an instanciated
    module, but will reflect some of it's properties better than ModuleType.
    """

    reserved_vars: set[str] = set(["meta"])
    """
    A list of variable names that are reserved and must not be set by the module.
    """

    def __init__(self):
        self.meta: HostMeta = cast('HostMeta', None)
        """
        The associated meta information
        """

class InventoryType(ModuleType):
    """
    A mockup type for inventory modules. This is not the actual type of an instanciated
    module, but will reflect some of it's properties better than ModuleType.
    """

    def __init__(self):
        self.hosts: list[Union[str, tuple[str, str]]] = []
        """
        The list of hosts that belong to this inventory and have to be loaded.
        """

class TaskType(ModuleType):
    """
    A mockup type for task modules. This is not the actual type of an instanciated
    module, but will reflect some of it's properties better than ModuleType.
    """

    reserved_vars: set[str] = set(["meta"])
    """
    A list of variable names that are reserved and must not be set by the module.
    """

    def __init__(self):
        self.meta: TaskMeta = cast('TaskMeta', None)
        """
        The associated meta information
        """
