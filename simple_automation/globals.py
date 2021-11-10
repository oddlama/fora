"""Stores all global state."""

import argparse

from typing import cast
from jinja2 import Environment

from .types import InventoryType, GroupType, HostType

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


jinja2_env: Environment = cast(Environment, NotYetLoaded())
"""
The jinja2 environment used for templating
"""
