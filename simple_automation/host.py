"""
Provides API for host definitions.
"""

from __future__ import annotations
from typing import Any, cast

from simple_automation import globals
from simple_automation.types import HostType

def name() -> str:
    """
    Returns the name of the host that is currently being defined.

    Return
    ----------
    str
        The name of the host.
    """
    if _this is None:
        raise RuntimeError("This function may only be called inside a host module definition.")
    return _this.name

def add_group(group: str):
    """
    Adds a this host to the specified group.

    Parameters
    ----------
    group
        The group
    """
    if _this is None:
        raise RuntimeError("This function may only be called inside a host module definition.")
    if group not in globals.groups:
        raise ValueError(f"Referenced invalid group '{group}'!")
    _this.groups.add(group)

def add_groups(groups: list[str]):
    """
    Adds a this host to the specified list of groups.

    Parameters
    ----------
    groups
        The groups
    """
    if _this is None:
        raise RuntimeError("This function may only be called inside a host module definition.")
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

    Raises
    ------
    AttributeError
        The given attribute was not found.
    """
    if attr.startswith("_") or attr in HostType.__annotations__:
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
    # pylint: disable=protected-access,import-outside-toplevel,cyclic-import
    import simple_automation.script
    if simple_automation.script._this is not None:
        if hasattr(simple_automation.script._this, attr):
            return getattr(simple_automation.script._this, attr)

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
    if attr.startswith("_") or attr in HostType.__annotations__:
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
    # pylint: disable=protected-access,import-outside-toplevel,cyclic-import
    import simple_automation.script
    if simple_automation.script._this is not None:
        if hasattr(simple_automation.script._this, attr):
            return True

    return False

_this: HostType = cast(HostType, None) # Cast None to ease typechecking in user code.
"""
This variable holds all meta information available to a host module when
it is being loaded. It must not be used anywhere else but inside the
definition (source) of the actual module.
"""

current_host: HostType = cast(HostType, None) # Cast None to ease typechecking in user code.
"""
The currently active host. Only set when a script is currently being executed on a host.
"""
