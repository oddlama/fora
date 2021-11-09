"""
This is the main module of simple_automation.
"""
from __future__ import annotations

import argparse

from typing import Optional, Union, Any, cast
from jinja2 import Environment

from .log import Logger
from .types import InventoryType, GroupType, HostType, ScriptType

class NotYetLoaded:
    """
    A dummy class which instances are used to provoke runtime-errors when
    using a part of simple_automation that hasn't been initialized yet.
    """

args: argparse.Namespace = cast(argparse.Namespace, NotYetLoaded())
"""
The global logger. Should be used for all user-facing information logging to ensure
that this information is displayed in a proper format and according to the user's
verbosity preferences.
"""

logger: Logger = Logger()
"""
The global logger. Should be used for all user-facing information logging to ensure
that this information is displayed in a proper format and according to the user's
verbosity preferences.
"""

inventory: InventoryType = cast(InventoryType, NotYetLoaded())
"""
The inventory module we are operating on.
This is loaded from the inventory definition file (inventory.py).
"""

available_groups: list[str] = cast(list[str], NotYetLoaded())
"""
All groups that will be available after loading. Useful to raise
errors early when referencing undefined groups.
"""

groups: dict[str, GroupType] = cast(dict[str, GroupType], NotYetLoaded())
"""
A dict containing all group modules loaded from groups/*.py, mapped by name.
"""

group_order: list[str] = cast(list[str], NotYetLoaded())
"""
A topological order of all groups, with highest precedence first.
"""

hosts: dict[str, HostType] = cast(dict[str, HostType], NotYetLoaded())
"""
A dict containing all host definitions, mapped by host_id.
"""


this: Union[GroupType, HostType, ScriptType] = cast(ScriptType, None) # Cast None to ease typechecking in user code.
"""
This variable holds all meta information available to a module when itself is being loaded.
The module can be a host, group or script module, and will hold an instance of the mockup type as defined in :module:`simple_automation.types`.
For more information on how to use the specific meta type objects, refer to the documentation of the respective class.

This variable must not be used anywhere else but inside the primary definition of one of the
aforementioned modules, otherwise it will be None.
"""

host: HostType = cast(HostType, None) # Cast None to ease typechecking in user code.
"""
The currently active host. Only set when a script is currently being executed on a host.
"""


jinja2_env: Environment = cast(Environment, NotYetLoaded())
"""
The jinja2 environment used for templating
"""


class SetVariableContextManager:
    """
    A context manager that sets a variable on enter and resets
    it to the previous value on exit.
    """
    def __init__(self, obj: object, var: str, value: Any):
        self.obj: object = obj
        self.var: str = var
        self.value: Any = value
        self.old_value: Any = getattr(self.obj, self.var)

    def __enter__(self):
        setattr(self.obj, self.var, self.value)

    def __exit__(self, exc_type, exc_value, trace):
        _ = (exc_type, exc_value, trace)
        setattr(self.obj, self.var, self.old_value)

def current_host(active_host: HostType):
    """
    A context manager to temporarily set :attr:`simple_automation.host` to the given value.
    """
    return SetVariableContextManager(__import__(__name__), 'host', active_host)

def set_this(value: Optional[Union[GroupType, HostType, ScriptType]]):
    """
    A context manager to temporarily set :attr:`simple_automation.this` to the given value.
    """
    return SetVariableContextManager(__import__(__name__), 'this', value)
