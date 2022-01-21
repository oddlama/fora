"""The main module of fora."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from fora.types import GroupWrapper, HostWrapper, ScriptWrapper
    from fora.inventory_wrapper import InventoryWrapper

inventory: InventoryWrapper = cast("InventoryWrapper", None)
"""
The inventory module we are operating on.
This is loaded from the inventory definition file.
"""

group: GroupWrapper = cast("GroupWrapper", None)
"""
This variable wraps the currently loaded group module.
It must not be accessed anywhere else but inside the
definition (source) of the actual group module.
"""

host: HostWrapper = cast("HostWrapper", None) # Cast None to ease typechecking in user code.
"""
This variable wraps the currently loaded hosts module (in case a host is just being defined),
or the currently active host while executing a script. It must not be used anywhere else
but inside the definition (source) of the actual module or inside of a script.
"""

script: ScriptWrapper = cast("ScriptWrapper", None) # Cast None to ease typechecking in user code.
"""This variable wraps the currently executed script module (if any)."""
