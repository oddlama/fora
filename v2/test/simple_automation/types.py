"""
Provides a mockup of types for the static type checker so it
has a better understanding of the dynamically loaded modules.
"""

from __future__ import annotations

from types import ModuleType
from typing import cast, Union, Any

import simple_automation
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

    meta: GroupMeta = cast(GroupMeta, None)

    @staticmethod
    def get_variables(group: GroupType) -> set[str]:
        """
        Returns the list of all user-defined attributes for a group.

        Parameters
        ----------
        group : GroupType
            The group module

        Returns
        -------
        set[str]
            The user-defined attributes for the given group
        """
        group_vars = set(attr for attr in dir(group) if
                         not callable(getattr(group, attr)) and
                         not attr.startswith("_") and
                         not isinstance(getattr(group, attr), ModuleType))
        group_vars -= GroupType.reserved_vars
        group_vars.remove('this')
        return group_vars

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

    @staticmethod
    def get_variables(host: HostType) -> set[str]:
        """
        Returns the list of all user-defined attributes for a host.

        Parameters
        ----------
        host : HostType
            The host module

        Returns
        -------
        set[str]
            The user-defined attributes for the given host
        """
        host_vars = set(attr for attr in dir(host) if
                         not callable(getattr(host, attr)) and
                         not attr.startswith("_") and
                         not isinstance(getattr(host, attr), ModuleType))
        host_vars -= HostType.reserved_vars
        host_vars.remove('this')
        return host_vars

    @staticmethod
    def getattr_hierarchical(host: HostType, attr: str) -> Any:
        """
        Looks up and returns the given attribute on the host's hierarchy in the following order:
          1. Host variables
          2. Group variables (respecting topological order), the global "all" group
             implicitly will be the last in the chain
          3. Task variables
          4. raises AttributeError

        If the attribute start with an underscore, the lookup will always be from the host object
        itself, and won't be propagated.

        Parameters
        ----------
        host : HostType
            The host on which we operate
        attr : str
            The attribute to get

        Returns
        -------
        Any
            The attributes value if it was found.
        """
        if attr.startswith("_"):
            if attr not in host.__dict__:
                raise AttributeError(attr)
            return host.__dict__[attr]

        # Look up variable on host module
        if attr in host.__dict__:
            return host.__dict__[attr]

        # Look up variable on groups
        for g in simple_automation.group_order:
            # Only consider a group if the host is in that group
            if g not in host.__dict__["meta"].groups:
                continue

            # Return the attribute if it is set on the group
            group = simple_automation.groups[g]
            if hasattr(group, attr):
                return getattr(group, attr)

        raise AttributeError(attr)

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

    meta: TaskMeta = cast(TaskMeta, None)

    @staticmethod
    def get_variables(task: TaskType) -> set[str]:
        """
        Returns the list of all user-defined attributes for a task.

        Parameters
        ----------
        task : TaskType
            The task module

        Returns
        -------
        set[str]
            The user-defined attributes for the given task
        """
        task_vars = set(attr for attr in dir(task) if
                         not callable(getattr(task, attr)) and
                         not attr.startswith("_") and
                         not isinstance(getattr(task, attr), ModuleType))
        task_vars -= TaskType.reserved_vars
        task_vars.remove('this')
        return task_vars
