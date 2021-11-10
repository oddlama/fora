"""
This is the main module of simple_automation.
"""
from __future__ import annotations

import argparse

from typing import Union, cast
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
A dict containing all group modules loaded from `groups/*.py`, mapped by name.
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
The module can be a host, group or script module, and will hold an instance of the mockup type as defined in :mod:`simple_automation.types`.
For more information on how to use the specific meta type objects, refer to the documentation of the respective class.

This variable must not be used anywhere else but inside the primary definition of one of the
aforementioned modules, otherwise it will be None.
"""

current_host: HostType = cast(HostType, None) # Cast None to ease typechecking in user code.
"""
The currently active host. Only set when a script is currently being executed on a host.
"""


jinja2_env: Environment = cast(Environment, NotYetLoaded())
"""
The jinja2 environment used for templating
"""
