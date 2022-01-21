"""
Provides a mockup of loadable module types. They are used to store metadata
that can be accessed by the module that is currently being loaded. These
types also help the static type checker, as it then has a better understanding
of the expected contents of the dynamically loaded modules.
"""

# This warning is too noisy, as it also triggers when importing
# inside functions below, which is done explicitly to avoid cyclic imports.
# pylint: disable=import-outside-toplevel,cyclic-import

from __future__ import annotations
import inspect

from dataclasses import dataclass, field
from types import ModuleType, TracebackType
from typing import TYPE_CHECKING, Any, Callable, Optional, Type, TypeVar, cast
from fora.remote_settings import RemoteSettings, ResolvedRemoteSettings

if TYPE_CHECKING:
    from fora.connection import Connection
    from fora.connectors.connector import Connector

T = TypeVar('T')

class RemoteDefaultsContext:
    """A context manager to overlay remote defaults on a stack of defaults."""
    def __init__(self, obj: ScriptWrapper, new_defaults: RemoteSettings):
        self.obj = obj
        self.new_defaults = new_defaults

    def __enter__(self) -> ResolvedRemoteSettings:
        # pylint: disable=import-outside-toplevel,cyclic-import
        import fora
        self.new_defaults = fora.host.connection.resolve_defaults(self.new_defaults)
        self.obj._defaults_stack.append(self.new_defaults)
        return cast(ResolvedRemoteSettings, fora.host.connection.base_settings.overlay(self.new_defaults))

    def __exit__(self, exc_type: Optional[Type[BaseException]], exc: Optional[BaseException], traceback: Optional[TracebackType]) -> None:
        _ = (exc_type, exc, traceback)
        self.obj._defaults_stack.pop()

class ModuleWrapper:
    """
    A module wrapper, that defaults attribute lookups to this object if the module doesn't define it.
    Derived classes must be annotated with @dataclass.
    """

    __annotations__: dict[str, Any]
    """Provided by the dataclass decorator."""

    module: Optional[ModuleType] = None
    """The dynamically loaded inventory module"""

    def __getattribute__(self, attr: str) -> Any:
        """Dynamic lookup will ensure that attributes on the module are used if available."""
        module = object.__getattribute__(self, "module")
        if attr == "__dict__":
            # Override `vars(obj)` to do correct fallback lookup
            d = object.__getattribute__(self, "__dict__")
            if module is not None:
                d = d.copy()
                d.update(module.__dict__)
            return d

        if attr.startswith("__") or module is None or not hasattr(module, attr):
            return object.__getattribute__(self, attr)
        return getattr(module, attr)

    def __setattr__(self, attr: str, value: Any) -> None:
        """Ensure that attributes are set on the wrapped module, if the module already has a corresponding attribute."""
        module = object.__getattribute__(self, "module")
        if attr.startswith("__") or module is None or not hasattr(module, attr):
            object.__setattr__(self, attr, value)
        else:
            module.__setattr__(attr, value)

    def is_overloaded(self, attr: str) -> Optional[bool]:
        """Returns NonoTrue if the given attribute exists as a variable on this wrapper but is overloaded by the wrapped module,
        False if the attribute exists on this wrapper but isn't overloaded and None if the attribute doesn't exist on this wrapper."""
        try:
            # try to get the attr from the wrapper.
            _ = object.__getattribute__(self, attr)
        except AttributeError:
            # attr doesn't exist on the wrapper class -> not overloaded, just a passthrough
            return None

        # Return true if the module overloads this wrapper's fallback
        module = object.__getattribute__(self, "module")
        if module is None:
            return False
        return hasattr(module, attr)

    def is_overridden(self, attr: str) -> bool:
        """Returns True if a variable has both been overloaded and changed."""
        module = object.__getattribute__(self, "module")
        return self.is_overloaded(attr) == True and getattr(module, attr) != object.__getattribute__(self, attr)

    def wrap(self, module: Any, copy_members: bool = False, copy_functions: bool = False) -> None:
        """
        Replaces the currently wrapped module (if any) with the given object.
        The module should be an instance of ModuleType in most cases, but doesn't need to be.
        Any object is supported.

        Parameters
        ----------
        module
            The new module to wrap.
        copy_members
            Copy all current member variables of this wrapper to the wrapped module.
            Excludes members starting with an underscore (`_`) and members of ModuleWrapper.
        copy_functions
            Copy all current member functions of this wrapper to the wrapped module,
            such that calling module.function(...) is forwarded to this wrapper's self.function(...).
            Excludes functions starting with an underscore (`_`) and functions of ModuleWrapper.
        """
        self.module = module
        if copy_members:
            for attr in self.__annotations__:
                if attr.startswith("_"):
                    continue
                setattr(self.module, attr, getattr(self, attr))

        if copy_functions:
            for attr,v in type(self).__dict__.items():
                if attr.startswith("_") or not callable(v):
                    continue
                setattr(self.module, attr, getattr(self, attr))

    def definition_file(self) -> str:
        """
        Returns the file from where the associated module has been loaded,
        or "<internal>" if no module file is associated with this wrapper.

        Returns
        -------
        str
            The file.
        """
        if self.module is None or not hasattr(self.module, '__file__') or self.module.__file__ is None:
            return "<internal>"
        return self.module.__file__

@dataclass
class GroupWrapper(ModuleWrapper):
    """
    A wrapper class for group modules. This will wrap any instanciated
    group to provide default attributes and methods for the group.

    All functions and members from this wrapper will be implicitly available
    on the wrapped group module. This means you can do the following

        after("desktops") # Higher precedence than desktops
        print(name)       # Access this group's name

    instead of having to first import the wrapper API:

        from fora import group as this

        this.after("desktops")
        print(this.name)
    """

    name: str
    """The name of the group. Must not be changed."""

    _groups_before: set[str] = field(default_factory=set)
    """This group was loaded before this set of other groups."""

    _groups_after: set[str] = field(default_factory=set)
    """This group was be loaded after this set of other groups."""

    def group_variables(self) -> set[str]:
        """
        Returns the list of all user-defined attributes for this group.

        Returns
        -------
        set[str]
            The user-defined attributes for this group
        """
        print("-------------------------", self)
        module_vars = set(attr for attr in dir(self.module) if
                            not attr.startswith("_") and
                            not isinstance(getattr(self.module, attr), ModuleType))
        module_vars -= set(GroupWrapper.__annotations__)
        module_vars -= set(GroupWrapper.__dict__)
        print(module_vars)
        return module_vars

@dataclass
class HostWrapper(ModuleWrapper):
    """
    A wrapper class for host modules. This will wrap any instanciated
    host to provide default attributes and methods for the host.

    All functions and members from this wrapper will be implicitly available
    on the wrapped host module. This means you can do the following

        url = "ssh://root@localhost" # Use this url to connect
        print(name)                  # Access this hosts's name

    instead of having to first import the wrapper API:

        from fora import group as this
        print(this.name)
    """

    name: str
    """The name that used to refer to this specific host. Must not be changed."""

    url: str
    """
    The url used to connect to this host. The schema in this url will be used to
    determine which connector implementation is used to establish a connection,
    if the `connector` has not been explicitly overridden by the module.
    This is determined just before a connection is initiated.

    By default, this field will reflect the value specified in the inventory,
    after url qualification.
    """

    groups: set[str] = field(default_factory=set)
    """The set of groups this host belongs to."""

    connector: Optional[Callable[[str, HostWrapper], Connector]] = None
    """The connector class to use. If `None`, the connector will be determined by the schema in the `url` when needed."""

    # Cast to ease typechecking in user code.
    connection: Connection = cast("Connection", None)
    """The active connection to this host, if one is opened."""

    def create_connector(self) -> Connector:
        """
        Creates a connector for this host.

        Raises
        ------
        FatalError
            The connector could not resolved because either an invalid connector was specified
            or the scheme could not be matched against existing connectors.

        Returns
        -------
        Connector
            A connector for this host
        """
        from fora.utils import FatalError
        from fora.connectors.connector import Connector
        if self.connector is not None:
            return self.connector(self.url, self)

        if ':' not in self.url:
            raise FatalError("url doesn't include a schema and no connector was specified explicitly", loc=self.definition_file())
        schema = self.url.split(':', maxsplit=1)[0]
        if schema not in Connector.registered_connectors:
            raise FatalError(f"no connector found for schema '{schema}'", loc=self.definition_file())
        return Connector.registered_connectors[schema](self.url, self)

    def __getattr__(self, attr: str) -> Any:
        """Variable lookup on the host has to fall back to a lookup on
        the currently active script."""
        from fora.utils import host_getattr_hierarchical
        return host_getattr_hierarchical(self, attr)

@dataclass
class ScriptWrapper(ModuleWrapper):
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

    _defaults_stack: list[RemoteSettings] = field(default_factory=lambda: [RemoteSettings()])
    """
    The stack of remote execution defaults. The stack must only be changed by using
    the context manager returned in `fora.script.defaults`.
    """

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

        This function is implicitly available on the wrapped script module.
        This means you can do the following

            with defaults(owner="root", file_mode="644", dir_mode="755"):
                # ... execute some operations

        instead of having to first import the wrapper API:

            from fora import script
            with script.defaults(owner="root", file_mode="644", dir_mode="755"):
                # ... execute some operations
        """
        def canonicalize_mode(mode: Optional[str]) -> Optional[str]:
            return None if mode is None else oct(int(mode, 8))[2:]

        requested_defaults = RemoteSettings(
                as_user=as_user,
                as_group=as_group,
                owner=owner,
                group=group,
                file_mode=canonicalize_mode(file_mode),
                dir_mode=canonicalize_mode(dir_mode),
                umask=canonicalize_mode(umask),
                cwd=cwd)

        # pylint: disable=import-outside-toplevel,cyclic-import
        import fora

        new_defaults = fora.host.connection.base_settings
        new_defaults = new_defaults.overlay(self.current_defaults())
        new_defaults = new_defaults.overlay(requested_defaults)
        return RemoteDefaultsContext(self, new_defaults)

    def current_defaults(self) -> RemoteSettings:
        """
        Returns the fully resolved currently active defaults.

        Returns
        -------
        RemoteSettings
            The currently active remote defaults.
        """
        return self._defaults_stack[-1]

    def Params(self, params_cls: Type[T]) -> Type[T]:
        """
        Decorator used to declare script parameters.

        This function is implicitly available on the wrapped script module.
        This means you can do the following

            @Params
            class params:
                my_parameter: str

        instead of having to first import the wrapper API:

            from fora import script

            @script.Params
            class params:
                my_parameter: str
        """
        _ = (self)
        # Find the calling site's module and get the passed parameters from there
        fi = inspect.stack()[1]
        params_dict: Optional[dict[str, Any]] = fi.frame.f_globals.get('_params', None)

        for param in params_cls.__annotations__:
            has_default = hasattr(params_cls, param)

            # Get the given parameter value, or the default value if none was supplied.
            # Raise an exception if no value was given but the parameter is required.
            if params_dict is None or param not in params_dict:
                if not has_default:
                    raise RuntimeError(f"This script requires parameter '{param}', but no such parameter was given.")
                value = getattr(params_cls, param)
            else:
                value = params_dict[param]

            setattr(params_cls, param, value)

        return params_cls
