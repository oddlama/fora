"""
This is the main module of simple_automation.
"""

from typing import Optional, Union, cast
from .types import InventoryType, GroupType, HostType, TaskType

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

tasks: dict[str, TaskType] = cast(dict[str, TaskType], NotYetLoaded())
"""
The list of all loaded task modules.
"""

host_id: Optional[str] = None
"""
The identifier of the host that is currently active or being loaded.
This corresponds to the identifier defined via hosts list in the inventory.
"""

host: HostType = cast(HostType, NotYetLoaded())
"""
The currently active host. Only set when a user script is being executed
and not while the host is being loaded.
"""

# TODO dict[str, Vault]
loaded_vaults: dict[str, int] = {}
"""
A list of all loaded and unlocked vaults. Used to prevent asking multiple times to decrypt the same vault.
"""

jinja2_env = NotYetLoaded()
"""
The jinja2 environment used for templating
"""
