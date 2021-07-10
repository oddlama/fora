"""
This is the main module of simple_automation.
"""

from typing import Optional, Union, Any, cast

import simple_automation.script
from .types import InventoryType, GroupType, HostType


class NotYetLoaded:
    """
    A dummy class which instances are used to provoke runtime-errors when
    using a part of simple_automation that hasn't been initialized yet.
    """

inventory = cast(InventoryType, NotYetLoaded())
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


_jinja2_env = NotYetLoaded()
"""
The jinja2 environment used for templating
"""


class SetVariableContextManager:
    """
    A context manager that sets a variable on enter and resets
    it to None on exit.
    """
    def __init__(self, obj: object, var: str, value: Any):
        self.obj: object = obj
        self.var: str = var
        self.value: Any = value

    def __enter__(self):
        setattr(self.obj, self.var, self.value)

    def __exit__(self, exc_type, exc_value, trace):
        setattr(self.obj, self.var, None)

def current_host(host: HostType):
    """
    A context manager to set the currently active host variable while it is active.
    """
    return SetVariableContextManager(simple_automation.script, 'host', host)

def set_temporary(obj: object, var: str, value: Any):
    """
    A context manager to set the given variable temporarily on the given object.
    """
    return SetVariableContextManager(obj, var, value)
