"""
Provides a mockup of loadable module types. They are used to store metadata
that can be accessed by the module that is currently being loaded. These
types also help the static type checker, as it then has a better understanding
of the expected contents of the dynamically loaded modules.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from types import ModuleType
from typing import TYPE_CHECKING, Any, Callable, Optional, Union, cast

from fora.remote_settings import RemoteSettings
if TYPE_CHECKING:
    from fora.connection import Connection
    from fora.connectors.connector import Connector

class MockupType(ModuleType):
    """
    A base class for all module mockup types, which allow a
    transfer of variables to a real dynamically loaded module.
    """

    __annotations__: dict[str, Any]
    """Provided by the dataclass decorator."""

    def __str__(self) -> str:
        return f"<'{getattr(self, 'name')}' from '{getattr(self, 'loaded_from')}'>"

    def transfer(self, module: ModuleType) -> None:
        """Transfers all annotated variables from this object to the given module."""
        for var in self.__annotations__:
            if hasattr(self, var):
                setattr(module, var, getattr(self, var))

@dataclass
class GroupType(MockupType):
    """
    A mockup type for group modules. This is not the actual type of an instanciated
    module, but will reflect some of it's properties better than ModuleType. While this
    class is mainly used to aid type-checking, its properties are transferred to the
    actual instanciated module before the module is executed.

    When writing a group module, you can use the API exposed in `fora.group`
    to access/change meta information about your module.

    Example: Using meta information `(groups/webserver.py)`
    ----

        from fora import group as this

        # Require that the 'servers' groups is processed before this group when resolving
        # variables for a host at execution time. This is important to avoid variable
        # definition ambiguity (which would be detected and reported as an error).
        this.after("server")
    """

    name: str
    """The name of the group. Must not be changed."""

    _loaded_from: str
    """The original file path of the instanciated module."""

    _groups_before: set[str] = field(default_factory=set)
    """This group will be loaded before this set of other groups."""

    _groups_after: set[str] = field(default_factory=set)
    """This group will be loaded after this set of other groups."""

@dataclass
class HostType(MockupType):
    """
    A mockup type for host modules. This is not the actual type of an instanciated
    module, but will reflect some of it's properties better than ModuleType. While this
    class is mainly used to aid type-checking, its properties are transferred to the
    actual instanciated module before the module is executed.

    When writing a host module, you can use the API exposed in `fora.host`
    to access/change meta information about your module.

    Example: Using meta information `(hosts/myhost.py)`
    ----

        from fora import host as this

        # Set the ssh host (useful if it differs from the name)
        ssh_host = "root@localhost"
        # Alternatively define a url, which allows to select a specific connection mechanism.
        url = "ssh://root@localhost"

        # The host's name used for instanciation as defined in the inventory
        print(this.name())

        # Add the host to a group
        this.add_group("desktops")
    """

    name: str
    """The corresponding host name as defined in the inventory. Must not be changed."""

    _loaded_from: str
    """The original file path of the instanciated module."""

    url: str
    """
    The url to the host. A matching connector for the schema must exist.
    Defaults to the name if not explicitly specified. Appends ssh:// if
    no schema is included in the name. Connection details can be given
    in the url schema or via attributes on the host module.
    """

    groups: set[str] = field(default_factory=set)
    """The set of groups this host belongs to."""

    connector: Optional[Callable[[str, HostType], Connector]] = None
    """The connector class to use. If unset the connector will be determined by the url."""

    connection: Connection = cast("Connection", None) # Cast None to ease typechecking in user code.
    """The connection to this host, if it is opened."""

@dataclass
class InventoryType(MockupType):
    """
    A mockup type for inventory modules. This is not the actual type of an instanciated
    module, but will reflect some of it's properties better than ModuleType.
    """

    hosts: list[Union[str, tuple[str, str]]] = field(default_factory=list)
    """The list of hosts that belong to this inventory and have to be loaded."""

@dataclass
class ScriptType(MockupType):
    """
    A mockup type for script modules. This is not the actual type of an instanciated
    module, but will reflect some of it's properties better than ModuleType. While this
    class is mainly used to aid type-checking, its properties are transferred to the
    actual instanciated module before the module is executed.

    When writing a script module, you can use the API exposed in `fora.script`
    to access/change meta information about your module.
    """

    name: str
    """The name of the script. Must not be changed."""

    _loaded_from: str
    """The original file path of the instanciated module."""

    _params: dict[str, Any] = field(default_factory=dict)
    """Parameters passed to the script (only set if the script isn't the main script)."""

    _defaults_stack: list[RemoteSettings] = field(default_factory=lambda: [RemoteSettings()])
    """
    The stack of remote execution defaults. The stack must only be changed by using
    the context manager returned in `fora.script.defaults`.
    """
