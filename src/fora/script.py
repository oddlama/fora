"""
Provides API for script definitions.
"""

import inspect
from types import TracebackType
from typing import Any, Optional, Type, TypeVar, cast

from fora.remote_settings import RemoteSettings, ResolvedRemoteSettings
from fora.types import ScriptType

T = TypeVar('T')

class RemoteDefaultsContext:
    """A context manager to overlay remote defaults on a stack of defaults."""
    def __init__(self, obj: ScriptType, new_defaults: RemoteSettings):
        self.obj = obj
        self.new_defaults = new_defaults

    def __enter__(self) -> ResolvedRemoteSettings:
        # pylint: disable=import-outside-toplevel,cyclic-import
        import fora.host
        self.new_defaults = fora.host.current_host.connection.resolve_defaults(self.new_defaults)
        self.obj._defaults_stack.append(self.new_defaults)
        return cast(ResolvedRemoteSettings, fora.host.current_host.connection.base_settings.overlay(self.new_defaults))

    def __exit__(self, exc_type: Optional[Type[BaseException]], exc: Optional[BaseException], traceback: Optional[TracebackType]) -> None:
        _ = (exc_type, exc, traceback)
        self.obj._defaults_stack.pop()

def defaults(as_user: Optional[str] = None,
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

        from fora.script import defaults
        with defaults(owner="root", file_mode="644", dir_mode="755"):
            # ...
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
    import fora.host

    new_defaults = fora.host.current_host.connection.base_settings
    new_defaults = new_defaults.overlay(current_defaults())
    new_defaults = new_defaults.overlay(requested_defaults)
    return RemoteDefaultsContext(_this, new_defaults)

def current_defaults() -> RemoteSettings:
    """
    Returns the fully resolved currently active defaults.

    Returns
    -------
    RemoteSettings
        The currently active remote defaults.
    """
    # pylint: disable=protected-access
    return _this._defaults_stack[-1]

def script_params(params_cls: Type[T]) -> Type[T]:
    """
    Decorator used to declare script parameters.

    Example: script.py

        from fora.script import script_params

        @script_params
        class params:
            my_parameter: str
    """
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

_this: ScriptType = cast(ScriptType, None) # Cast None to ease typechecking in user code.
"""
This variable holds all meta information available to a script module when
it is being loaded. It must not be used anywhere else but inside the
definition (source) of the actual module.
"""
