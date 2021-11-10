"""
Provides API for script definitions.
"""

import inspect
from typing import Any, Optional, cast

import simple_automation.host
from simple_automation.remote_settings import RemoteSettings, ResolvedRemoteSettings, base_settings
from simple_automation.types import ScriptType

class RemoteDefaultsContext:
    """A context manager to overlay remote defaults on a stack of defaults."""
    def __init__(self, obj: ScriptType, new_defaults: RemoteSettings):
        self.obj = obj
        self.new_defaults = new_defaults

    def __enter__(self) -> ResolvedRemoteSettings:
        self.new_defaults = simple_automation.host.current_host.connection.resolve_defaults(self.new_defaults)
        self.obj._defaults_stack.append(self.new_defaults)
        return cast(ResolvedRemoteSettings, base_settings.overlay(self.new_defaults))

    def __exit__(self, type_t, value, traceback):
        _ = (type_t, value, traceback)
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

        from simple_automation.script import this
        with this.defaults(owner="root", file_mode="644", dir_mode="755"):
            # ...
    """
    new_defaults = RemoteSettings(
                as_user=as_user,
                as_group=as_group,
                owner=owner,
                group=group,
                file_mode=None if file_mode is None else oct(int(file_mode, 8))[2:],
                dir_mode=None if dir_mode is None else oct(int(dir_mode, 8))[2:],
                umask=None if umask is None else oct(int(umask, 8))[2:],
                cwd=cwd)
    new_defaults = this._defaults_stack[-1].overlay(new_defaults)
    return RemoteDefaultsContext(this, new_defaults)

def current_defaults() -> RemoteSettings:
    """
    Returns the fully resolved currently active defaults.

    Returns
    -------
    RemoteSettings
        The currently active remote defaults.
    """
    return base_settings.overlay(this._defaults_stack[-1])

this: ScriptType = cast(ScriptType, None) # Cast None to ease typechecking in user code.
"""
This variable holds all meta information available to a script module when
it is being loaded. It must not be used anywhere else but inside the
definition (source) of the actual module.
"""

# TODO make defaults a module level method

def script_params(params_cls):
    """
    Decorator used to declare script parameters.

    Example: script.py

        from simple_automation.script import script_params

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
