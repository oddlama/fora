"""
Provides a mockup of types for the static type checker so it
has a better understanding of the dynamically loaded modules.
"""

from __future__ import annotations

from types import ModuleType
from typing import Union, Any

# pylint: disable=cyclic-import
# Cyclic import is correct at this point, as this module will not access anything from simple_automation
# when it is being loaded, but only when certain functions are used.
import simple_automation

class MockupType(ModuleType):
    """
    A base class for all module mockup types.
    """

    reserved_vars: set[str] = set()
    """
    A set of reserved variables. Defined by the subclass.
    """

    def __str__(self):
        return f"<'{getattr(self, 'name')}' from '{getattr(self, 'loaded_from')}'>"

    def transfer(self, module: ModuleType):
        """
        Transfers all reserved variables from this object to the given module.
        """
        for var in self.reserved_vars:
            setattr(module, var, getattr(self, var))

class GroupType(MockupType):
    """
    A mockup type for group modules. This is not the actual type of an instanciated
    module, but will reflect some of it's properties better than ModuleType.

    This class also represents all meta information available to a group module when itself
    is being loaded. It allows a module to access and modify its associated meta-information.
    After the module has been loaded, the meta information will be transferred directly to the module.

    When writing a group module, you can simply import :attr:`simple_automation.this`,
    which exposes an API to access/modify this information.

    .. topic:: Example: Using meta information (groups/webserver.py)

        .. code-block:: python

            from simple_automation import this

            # Require that the 'servers' groups is processed before this group when resolving
            # variables for a host at execution time. This is important to avoid variable
            # definition ambiguity (which would be detected and reported as an error).
            this.after("server")
    """

    reserved_vars: set[str] = set(["name", "loaded_from", "groups_before", "groups_after"])
    """
    A list of variable names that are reserved and must not be set by the module.
    """

    def __init__(self, name: str, loaded_from: str):
        self.name: str = name
        """
        The name of the group. Must not be changed.
        """

        self.loaded_from: str = loaded_from
        """
        The original file path of the instanciated module.
        """

        self.groups_before: set[str] = set()
        """
        This group will be loaded before this set of other groups.
        """

        self.groups_after: set[str] = set()
        """
        This group will be loaded after this set of other groups.
        """

    def before(self, group: str):
        """
        Adds a reverse-dependency on the given group.

        Parameters
        ----------
        group : str
            The group that must be loaded before this group.
        """
        if group not in simple_automation.available_groups:
            raise ValueError(f"Referenced invalid group '{group}'!")
        if group == self.name:
            raise ValueError("Cannot add reverse-dependency to self!")

        self.groups_before.add(group)

    def before_all(self, groups: list[str]):
        """
        Adds a reverse-dependency on all given groups.

        Parameters
        ----------
        groups : list[str]
            The groups
        """
        for g in groups:
            self.before(g)

    def after(self, group: str):
        """
        Adds a dependency on the given group.

        Parameters
        ----------
        group : str
            The group that must be loaded after this group.
        """
        if group not in simple_automation.available_groups:
            raise ValueError(f"Referenced invalid group '{group}'!")
        if group == self.name:
            raise ValueError("Cannot add dependency to self!")

        self.groups_after.add(group)

    def after_all(self, groups: list[str]):
        """
        Adds a dependency on all given groups.

        Parameters
        ----------
        groups : list[str]
            The groups
        """
        for g in groups:
            self.after(g)

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
        return _get_variables(GroupType, group)

class HostType(MockupType):
    """
    A mockup type for host modules. This is not the actual type of an instanciated
    module, but will reflect some of it's properties better than ModuleType.

    This class also represents all meta information available to a host module when itself is being loaded.
    It allows a module to access and modify its associated meta-information. After the module
    has been loaded, the meta information will be transferred directly to the module.

    When writing a host module, you can simply import :attr:`simple_automation.this`,
    which exposes an API to access/modify this information.

    .. topic:: Example: Using meta information (hosts/myhost.py)

        .. code-block:: python

            from simple_automation import this

            # The host name used for instanciation as defined in the inventory
            print(this.name)

            # Set the ssh host (useful if it differs from the name)
            this.ssh_host = "root@localhost"

            # Add the host to a group
            this.add_group("desktops")
    """

    reserved_vars: set[str] = set(["name", "loaded_from", "ssh_host", "ssh_port", "ssh_opts", "groups"])
    """
    A list of variable names that are reserved and must not be set by the module.
    """

    def __init__(self, host_id: str, loaded_from: str):
        self.name: str = host_id
        """
        The corresponding host name as defined in the inventory.
        Must not be changed.
        """

        self.loaded_from: str = loaded_from
        """
        The original file path of the instanciated module.
        """

        self.ssh_host: str = host_id
        """
        The ssh destination as accepted by ssh(1).
        """

        self.ssh_port: int = 22
        """
        The port used to for ssh connections.
        """

        self.ssh_opts: list[str] = []
        """
        Additional options to the ssh command for this host.
        """

        self.groups: set[str] = set()
        """
        The set of groups this host belongs to.
        """

    def add_group(self, group: str):
        """
        Adds a this host to the specified group.

        Parameters
        ----------
        group : str
            The group
        """
        if group not in simple_automation.groups:
            raise ValueError(f"Referenced invalid group '{group}'!")
        self.groups.add(group)

    def add_groups(self, groups: list[str]):
        """
        Adds a this host to the specified list of groups.

        Parameters
        ----------
        groups : list[str]
            The groups
        """
        for g in groups:
            self.add_group(g)

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
            if g not in host.__dict__["groups"]:
                continue

            # Return the attribute if it is set on the group
            group = simple_automation.groups[g]
            if hasattr(group, attr):
                return getattr(group, attr)

        # TODO task variables lookup here
        # if simple_automation.task is not None:
        #    if hasattr(simple_automation.task, attr):
        #        return getattr(simple_automation.task, attr)

        raise AttributeError(attr)

    @staticmethod
    def hasattr_hierarchical(host: HostType, attr: str) -> Any:
        """
        Checks whether the given attribute exists in the host's hierarchy.
        Checks are done in the following order:
          1. Host variables
          2. Group variables (respecting topological order), the global "all" group
             implicitly will be the last in the chain
          3. Task variables
          4. False

        If the attribute start with an underscore, the lookup will always be from the host object
        itself, and won't be propagated.

        Parameters
        ----------
        host : HostType
            The host on which we operate
        attr : str
            The attribute to check

        Returns
        -------
        bool
            True if the attribute exists
        """
        if attr.startswith("_"):
            return attr in host.__dict__

        # Look up variable on host module
        if attr in host.__dict__:
            return True

        # Look up variable on groups
        for g in simple_automation.group_order:
            # Only consider a group if the host is in that group
            if g not in host.__dict__["groups"]:
                continue

            # Return the attribute if it is set on the group
            group = simple_automation.groups[g]
            if hasattr(group, attr):
                return True

        # TODO task variables lookup here
        # if simple_automation.task is not None:
        #    if hasattr(simple_automation.task, attr):
        #        return True

        return False

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
        return _get_variables(HostType, host)

class InventoryType(MockupType):
    """
    A mockup type for inventory modules. This is not the actual type of an instanciated
    module, but will reflect some of it's properties better than ModuleType.
    """

    def __init__(self):
        self.hosts: list[Union[str, tuple[str, str]]] = []
        """
        The list of hosts that belong to this inventory and have to be loaded.
        """

class TaskType(MockupType):
    """
    A mockup type for task modules. This is not the actual type of an instanciated
    module, but will reflect some of it's properties better than ModuleType.

    This class also represents all meta information available to a task module when itself
    is being loaded. It allows a module to access and modify its associated meta-information.
    After the module has been loaded, the meta information will be transferred directly to the module.

    When writing a task module, you can simply import :attr:`simple_automation.this`,
    which exposes an API to access/modify this information.
    """

    reserved_vars: set[str] = set(["name", "loaded_from"])
    """
    A list of variable names that are reserved and must not be set by the module.
    """

    def __init__(self, host_id: str, loaded_from: str):
        self.name: str = host_id
        """
        The name of the task. Must not be changed.
        """

        self.loaded_from: str = loaded_from
        """
        The original file path of the instanciated module.
        """

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
        return _get_variables(TaskType, task)

class ScriptType(MockupType):
    """
    A mockup type for script modules. This is not the actual type of an instanciated
    module, but will reflect some of it's properties better than ModuleType.

    This class also represents all meta information available to a script module when itself
    is being loaded. It allows a module to access and modify its associated meta-information.
    After the module has been loaded, the meta information will be transferred directly to the module.

    When writing a script module, you can simply import :attr:`simple_automation.this`,
    which exposes an API to access/modify this information.
    """

    reserved_vars: set[str] = set(["name", "loaded_from"])
    """
    A list of variable names that are reserved and must not be set by the module.
    """

    def __init__(self, host_id: str, loaded_from: str):
        self.name: str = host_id
        """
        The name of the script. Must not be changed.
        """

        self.loaded_from: str = loaded_from
        """
        The original file path of the instanciated module.
        """

    @staticmethod
    def get_variables(script: ScriptType) -> set[str]:
        """
        Returns the list of all user-defined attributes for a script.

        Parameters
        ----------
        script : ScriptType
            The script module

        Returns
        -------
        set[str]
            The user-defined attributes for the given script
        """
        return _get_variables(ScriptType, script)

def _get_variables(cls, module: ModuleType) -> set[str]:
    """
    Returns the list of all user-defined attributes for the given module.

    Parameters
    ----------
    cls
        The mockup class of the given module (GroupType, HostType, ...)
    module : ModuleType
        The given module

    Returns
    -------
    set[str]
        The user-defined attributes for the given module
    """
    module_vars = set(attr for attr in dir(module) if
                     not callable(getattr(module, attr)) and
                     not attr.startswith("_") and
                     not isinstance(getattr(module, attr), ModuleType))
    module_vars -= cls.reserved_vars
    module_vars.remove('this')
    return module_vars
