"""
Provides a mockup of loadable module types. They are used to store metadata
that can be accessed by the module that is currently being loaded. These
types also help the static type checker, as it then has a better understanding
of the expected contents of the dynamically loaded modules.
"""

from __future__ import annotations
from dataclasses import dataclass
from types import ModuleType
from typing import Any, Callable, Optional, Union, cast

from simple_automation.connection import Connection
from simple_automation.connectors.connector import Connector
from simple_automation.remote_settings import RemoteSettings

class MockupType(ModuleType):
    """
    A base class for all module mockup types, which allow a
    transfer of variables to a real dynamically loaded module.
    """

    reserved_vars: set[str] = set()
    """A set of reserved variables. Defined by the subclass."""

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

# TODO make Example a section in the sphinx documentation
@dataclass
class GroupType(MockupType):
    """
    A mockup type for group modules. This is not the actual type of an instanciated
    module, but will reflect some of it's properties better than ModuleType.

    This class also represents all meta information available to a group module when itself
    is being loaded. It allows a module to access and modify its associated meta-information.
    After the module has been loaded, the meta information will be transferred directly to the module.

    When writing a group module, you can simply import :attr:`simple_automation.group.this`,
    which exposes an API to access/modify this information.

    Example: Using meta information (groups/webserver.py)

    .. code-block:: python

        from simple_automation.group import this

        # Require that the 'servers' groups is processed before this group when resolving
        # variables for a host at execution time. This is important to avoid variable
        # definition ambiguity (which would be detected and reported as an error).
        this.after("server")
    """

    name: str
    """The name of the group. Must not be changed."""

    loaded_from: str
    """The original file path of the instanciated module."""

    module: ModuleType = cast(ModuleType, None)
    """The associated dynamically loaded module (will be set before the dynamic module is executed). """

    groups_before: set[str] = set()
    """This group will be loaded before this set of other groups."""

    groups_after: set[str] = set()
    """This group will be loaded after this set of other groups."""

# TODO: make Example a section in the sphinx documentation
@dataclass
class HostType(MockupType):
    """
    A mockup type for host modules. This is not the actual type of an instanciated
    module, but will reflect some of it's properties better than ModuleType.

    This class also represents all meta information available to a host module when itself is being loaded.
    It allows a module to access and modify its associated meta-information. After the module
    has been loaded, the meta information will be transferred directly to the module.

    When writing a host module, you can simply import :attr:`simple_automation.host.this`,
    which exposes an API to access/modify this information.

    Example: Using meta information (hosts/myhost.py)

    .. code-block:: python

        from simple_automation.host import this

        # The host name used for instanciation as defined in the inventory
        print(this.name)

        # Set the ssh host (useful if it differs from the name)
        this.ssh_host = "root@localhost"

        # Add the host to a group
        this.add_group("desktops")
    """

    name: str
    """The corresponding host name as defined in the inventory. Must not be changed."""

    loaded_from: str
    """The original file path of the instanciated module."""

    module: ModuleType = cast(ModuleType, None)
    """The associated dynamically loaded module (will be set before the dynamic module is executed). """

    groups: set[str] = set()
    """The set of groups this host belongs to."""

    url: str = "ssh:"
    """
    The url to the host. A matching connector for the schema must exist.
    Defaults to an ssh connection if not explicitly specified. Connection
    details can be given in the url schema or via attributes on the host module.
    """

    connector: Optional[Callable[[str, HostType], Connector]] = None
    """The connector class to use. If unset the connector will be determined by the url."""

    connection: Connection = cast(Connection, None) # Cast None to ease typechecking in user code.
    """The connection to this host, if it is opened."""

@dataclass
class InventoryType(MockupType):
    """
    A mockup type for inventory modules. This is not the actual type of an instanciated
    module, but will reflect some of it's properties better than ModuleType.
    """

    hosts: list[Union[str, tuple[str, str]]] = []
    """The list of hosts that belong to this inventory and have to be loaded."""

@dataclass
class ScriptType(MockupType):
    """
    A mockup type for script modules. This is not the actual type of an instanciated
    module, but will reflect some of it's properties better than ModuleType.

    This class also represents all meta information available to a script module when itself
    is being loaded. It allows a module to access and modify its associated meta-information.

    When writing a script module, you can simply import :attr:`simple_automation.script.this`,
    which exposes an API to access/modify this information.
    """

    name: str
    """The name of the script. Must not be changed."""

    loaded_from: str
    """The original file path of the instanciated module."""

    module: ModuleType = cast(ModuleType, None)
    """The associated dynamically loaded module (will be set before the dynamic module is executed). """

    _params: dict[str, Any] = {}
    """Parameters passed to the script (only set if the script isn't the main script)."""

    _defaults_stack: list[RemoteSettings] = [RemoteSettings()]
    """
    The stack of remote execution defaults. The stack must only be changed by using
    the context manager returned in :meth:`defaults() <simple_automation.script.defaults>`.
    """
