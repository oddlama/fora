"""
Provides api for script definitions.
"""

import inspect
from typing import Any, Optional, cast

from simple_automation.types import MockupType

class ScriptType(MockupType):
    """
    A mockup type for script modules. This is not the actual type of an instanciated
    module, but will reflect some of it's properties better than ModuleType.

    This class also represents all meta information available to a script module when itself
    is being loaded. It allows a module to access and modify its associated meta-information.

    When writing a script module, you can simply import :attr:`simple_automation.script.this`,
    which exposes an API to access/modify this information.
    """

    reserved_vars: set[str] = set(["module", "name", "loaded_from", "_params"])
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

        self._params: dict[str, Any]
        """
        Parameters passed to the script (only set if the script isn't the main script).
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

            from simple_automation.script import this
            with this.defaults(owner="root", file_mode="644", dir_mode="755"):
                # ...
        """
        if simple_automation.script.this is not self:
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
        return base_settings.overlay(self._defaults_stack[-1])

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
