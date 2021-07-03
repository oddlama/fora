"""
This is the main module of simple_automation.
"""

from typing import Optional, Union, cast
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

groups: dict[str, GroupType] = cast(dict[str, GroupType], NotYetLoaded())
"""
The list of all group modules loaded from groups/*.py.
"""

group_order: list[str] = cast(list[str], NotYetLoaded())
"""
A topological order of all groups
"""

hosts: list[HostType] = cast(list[HostType], NotYetLoaded())
"""
The list of all instanciated host modules, after they were all loaded.
"""


# TODO name clash with submodule
_host: HostType = cast(HostType, None)
"""
The currently active host. Only set when a user script is being executed
and not while the host is being loaded.
"""


_jinja2_env = NotYetLoaded()
"""
The jinja2 environment used for templating
"""
