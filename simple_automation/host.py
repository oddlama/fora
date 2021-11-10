"""
Provides API for host definitions.
"""

from __future__ import annotations

from typing import Any, cast

import simple_automation.host
import simple_automation.script

from simple_automation import globals
from simple_automation.types import HostType, ScriptType

def add_group(group: str):
    """
    Adds a this host to the specified group.

    Parameters
    ----------
    group
        The group
    """
    if group not in globals.groups:
        raise ValueError(f"Referenced invalid group '{group}'!")
    this.groups.add(group)

def add_groups(groups: list[str]):
    """
    Adds a this host to the specified list of groups.

    Parameters
    ----------
    groups
        The groups
    """
    for g in groups:
        add_group(g)

def getattr_hierarchical(host: HostType, attr: str) -> Any:
    """
    Looks up and returns the given attribute on the host's hierarchy in the following order:
        1. Host variables
        2. Group variables (respecting topological order), the global "all" group
            implicitly will be the last in the chain
        3. Script variables
        4. raises AttributeError

    If the attribute start with an underscore, the lookup will always be from the host object
    itself, and won't be propagated.

    Parameters
    ----------
    host
        The host on which we operate
    attr
        The attribute to get

    Returns
    -------
    Any
        The attributes value if it was found.
    """
    if attr.startswith("_"):
        if attr not in host.__dict__:
            raise AttributeError(attr)
        return host.__dict__[attr]

    # Look up variable on host module
    if attr in host.__dict__:
        return host.__dict__[attr]

    # Look up variable on groups
    for g in globals.group_order:
        # Only consider a group if the host is in that group
        if g not in host.__dict__["groups"]:
            continue

        # Return the attribute if it is set on the group
        group = globals.groups[g]
        if hasattr(group, attr):
            return getattr(group, attr)

    # Look up variable on current script
    if isinstance(simple_automation.script.this, ScriptType):
        if hasattr(simple_automation.script.this.module, attr):
            return getattr(simple_automation.script.this.module, attr)

    raise AttributeError(attr)

def hasattr_hierarchical(host: HostType, attr: str) -> Any:
    """
    Checks whether the given attribute exists in the host's hierarchy.
    Checks are done in the following order:

        1. Host variables
        2. Group variables (respecting topological order), the global "all" group
            implicitly will be the last in the chain
        3. Script variables
        4. False

    If the attribute start with an underscore, the lookup will always be from the host object
    itself, and won't be propagated.

    Parameters
    ----------
    host
        The host on which we operate
    attr
        The attribute to check

    Returns
    -------
    bool
        True if the attribute exists
    """
    if attr.startswith("_"):
        return attr in host.__dict__

    # Look up variable on host module
    if attr in host.__dict__:
        return True

    # Look up variable on groups
    for g in globals.group_order:
        # Only consider a group if the host is in that group
        if g not in host.__dict__["groups"]:
            continue

        # Return the attribute if it is set on the group
        group = globals.groups[g]
        if hasattr(group, attr):
            return True

    # Look up variable on current script
    if isinstance(simple_automation.script.this, ScriptType):
        if hasattr(simple_automation.script.this.module, attr):
            return True

    return False

this: HostType = cast(HostType, None) # Cast None to ease typechecking in user code.
"""
This variable holds all meta information available to a host module when
it is being loaded. It must not be used anywhere else but inside the
definition (source) of the actual module.
"""

current_host: HostType = cast(HostType, None) # Cast None to ease typechecking in user code.
"""
The currently active host. Only set when a script is currently being executed on a host.
"""
