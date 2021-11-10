"""
Provides a mockup of loadable module types. They are used to store metadata
that can be accessed by the module that is currently being loaded. These
types also help the static type checker, as it then has a better understanding
of the expected contents of the dynamically loaded modules.
"""

from __future__ import annotations

from types import ModuleType
from typing import Union, Callable, Optional, Any, cast, TYPE_CHECKING
import functools

# pylint: disable=cyclic-import
# Cyclic import is correct at this point, as this module will not access anything from simple_automation
# when it is being loaded, but only when certain functions are used.
import simple_automation
import simple_automation.script
from simple_automation.remote_settings import RemoteSettings, ResolvedRemoteSettings, base_settings

if TYPE_CHECKING:
    from simple_automation.connection import Connection
    from simple_automation.connectors.connector import Connector

# TODO: needed? how many function do we actually wanna transfer?
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

    def __enter__(self) -> ResolvedRemoteSettings:
        self.new_defaults = simple_automation.current_host.connection.resolve_defaults(self.new_defaults)
        self.obj._defaults_stack.append(self.new_defaults)
        return cast(ResolvedRemoteSettings, base_settings.overlay(self.new_defaults))

    def __exit__(self, type_t, value, traceback):
        _ = (type_t, value, traceback)
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

def _get_variables(cls, module: ModuleType) -> set[str]:
    """
    Returns the list of all user-defined attributes for the given module.

    Parameters
    ----------
    cls
        The mockup class of the given module (GroupType, HostType, ...)
    module
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
