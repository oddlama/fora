"""The main module of fora."""

from typing import cast
from fora.types import GroupWrapper, InventoryWrapper

inventory: InventoryWrapper = InventoryWrapper()
"""
The inventory module we are operating on.
This is loaded from the inventory definition file.
"""

group: GroupWrapper = cast(GroupWrapper, None)
"""
This variable wraps the currently loaded group module.
It must not be accessed anywhere else but inside the
definition (source) of the actual group module.
"""
