"""
Provides a mockup of loadable module types. They are used to store metadata
that can be accessed by the module that is currently being loaded. These
types also help the static type checker, as it then has a better understanding
of the expected contents of the dynamically loaded modules.
"""

from __future__ import annotations

from types import ModuleType
from typing import Union, Callable, Optional, Any, TYPE_CHECKING
import functools

# pylint: disable=cyclic-import
# Cyclic import is correct at this point, as this module will not access anything from simple_automation
# when it is being loaded, but only when certain functions are used.
import simple_automation
from simple_automation.remote_settings import RemoteSettings

if TYPE_CHECKING:
    from simple_automation.connection import Connection
    from simple_automation.connectors.connector import Connector

def transfer(function):
    """
    A decorator for implementations of MockupType. This will cause
    the decorated function to be transferred to the loaded dynamic module,
    after variables have been transferred, but before the dynamic module is executed.
    """
    setattr(function, '_transfer', True)
    return function

class RemoteDefaultsContext:
    """
    A context manager to overlay remote defaults on a stack of defaults.
    """
    def __init__(self, obj: ScriptType, new_defaults: RemoteSettings):
        self.obj = obj
        self.new_defaults = new_defaults

    def __enter__(self):
        self.new_defaults = simple_automation.host.connection.resolve_defaults(self.new_defaults)
        self.obj._defaults_stack.append(self.new_defaults)
        return RemoteSettings.base_settings.overlay(self.new_defaults)

    def __exit__(self, type_t, value, traceback):
        self.obj._defaults_stack.pop()

class MockupType(ModuleType):
    """
    A base class for all module mockup types, which allow a
    transfer of variables to a real dynamically loaded module.
    """

    reserved_vars: set[str] = set()
    """
    A set of reserved variables. Defined by the subclass.
    """

    def __str__(self):
        return f"<'{getattr(self, 'name')}' from '{getattr(self, 'loaded_from')}'>"

    def transfer(self, module: ModuleType):
        """
        Transfers all reserved variables from this object to the given module,
        as well as any functions tagged with @transfer.
        """
        for var in self.reserved_vars:
            if hasattr(self, var):
                setattr(module, var, getattr(self, var))

        # Transfer functions tagged with @transfer
        for attr in dir(type(self)):
            a = getattr(self, attr)
            if callable(a) and hasattr(a, '_transfer') and getattr(a, '_transfer') is True:
                setattr(module, attr, functools.partial(getattr(self, attr), module))

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

    reserved_vars: set[str] = set(["module", "name", "loaded_from", "groups_before", "groups_after"])
    """
    A list of variable names that are reserved and must not be set by the module.
    """

    def __init__(self, name: str, loaded_from: str):
        self.module: ModuleType
        """
        The associated dynamically loaded module (will be set before the dynamic module is executed).
        """

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

    @transfer
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

    @transfer
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

    @transfer
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

    @transfer
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

    reserved_vars: set[str] = set(["module", "name", "loaded_from", "groups", "url", "connector", "connection"])
    """
    A list of variable names that are reserved and must not be set by the module.
    """

    def __init__(self, host_id: str, loaded_from: str):
        self.module: ModuleType
        """
        The associated dynamically loaded module (will be set before the dynamic module is executed).
        """

        self.name: str = host_id
        """
        The corresponding host name as defined in the inventory.
        Must not be changed.
        """

        self.loaded_from: str = loaded_from
        """
        The original file path of the instanciated module.
        """

        self.groups: set[str] = set()
        """
        The set of groups this host belongs to.
        """

        self.url: str = "ssh:"
        """
        The url to the host. A matching connector for the schema must exist.
        Defaults to an ssh connection if unset. Connection details can be given in the url
        or via attributes on the host module.
        """

        self.connector: Optional[Callable[[str, HostType], Connector]] = None
        """
        The connector class to use. If unset the connector will be determined by the url.
        """

        self.connection: Optional[Connection] = None
        """
        The connection to this host, if it is opened.
        """

    @transfer
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

    @transfer
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
          3. Script variables
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

        # Look up variable on current script
        if isinstance(simple_automation.this, ScriptType):
            if hasattr(simple_automation.this.module, attr):
                return getattr(simple_automation.this.module, attr)

        raise AttributeError(attr)

    @staticmethod
    def hasattr_hierarchical(host: HostType, attr: str) -> Any:
        """
        Checks whether the given attribute exists in the host's hierarchy.
        Checks are done in the following order:
          1. Host variables
          2. Group variables (respecting topological order), the global "all" group
             implicitly will be the last in the chain
          3. Script variables
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

        # Look up variable on current script
        if isinstance(simple_automation.this, ScriptType):
            if hasattr(simple_automation.this.module, attr):
                return True

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

class ScriptType(MockupType):
    """
    A mockup type for script modules. This is not the actual type of an instanciated
    module, but will reflect some of it's properties better than ModuleType.

    This class also represents all meta information available to a script module when itself
    is being loaded. It allows a module to access and modify its associated meta-information.

    When writing a script module, you can simply import :attr:`simple_automation.this`,
    which exposes an API to access/modify this information.
    """

    reserved_vars: set[str] = set(["module", "name", "loaded_from"])
    """
    A list of variable names that are reserved and must not be set by the module.
    """

    def __init__(self, host_id: str, loaded_from: str):
        self.module: ModuleType
        """
        The associated dynamically loaded module (will be set before the dynamic module is executed).
        """

        self.name: str = host_id
        """
        The name of the script. Must not be changed.
        """

        self.loaded_from: str = loaded_from
        """
        The original file path of the instanciated module.
        """

        self._defaults_stack: list[RemoteSettings] = [RemoteSettings()]
        """
        The stack of remote execution defaults. The stack must only be changed by using
        the context manager returned in :meth:`self.defaults() <simple_automation.types.ScriptType.defaults>`.
        """

    @transfer
    def defaults(self,
                 as_user: Optional[str] = None,
                 as_group: Optional[str] = None,
                 owner: Optional[str] = None,
                 group: Optional[str] = None,
                 file_mode: Optional[str] = None,
                 dir_mode: Optional[str] = None,
                 umask: Optional[str] = None,
                 cwd: Optional[str] = None) -> RemoteDefaultsContext:
        """
        Returns a context manager to incrementally change the remote execution defaults.

        .. code-block:: python

            from simple_automation import this
            with this.defaults(owner="root", file_mode="644", dir_mode="755"):
                # ...
        """
        if simple_automation.this is not self:
            raise RuntimeError("Cannot set defaults on a script when it isn't the currently active script.")

        new_defaults = RemoteSettings(
                 as_user=as_user,
                 as_group=as_group,
                 owner=owner,
                 group=group,
                 file_mode=None if file_mode is None else oct(int(file_mode, 8))[2:],
                 dir_mode=None if dir_mode is None else oct(int(dir_mode, 8))[2:],
                 umask=None if umask is None else oct(int(umask, 8))[2:],
                 cwd=cwd)
        new_defaults = self._defaults_stack[-1].overlay(new_defaults)
        return RemoteDefaultsContext(self, new_defaults)

    @transfer
    def current_defaults(self) -> RemoteSettings:
        """
        Returns the fully resolved currently active defaults.

        Returns
        -------
        RemoteSettings
            The currently active remote defaults.
        """
        return RemoteSettings.base_settings.overlay(self._defaults_stack[-1])

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
