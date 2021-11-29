"""
Provides API for host definitions.
"""

from __future__ import annotations
from types import ModuleType
from typing import Any, cast

from fora import globals as G
from fora.types import GroupType, HostType, ScriptType

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

def add_group(group: str) -> None:
    """
    Adds a this host to the specified group.

    Parameters
    ----------
    group
        The group
    """
    if _this is None:
        raise RuntimeError("This function may only be called inside a host module definition.")
    if group not in G.groups:
        raise ValueError(f"Referenced invalid group '{group}'!")
    _this.groups.add(group)

def add_groups(groups: list[str]) -> None:
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

def _is_normal_var(attr: str, value: Any) -> bool:
    """Returns True if the attribute doesn't start with an underscore, and is not a module."""
    return not attr.startswith("_") \
            and not isinstance(value, ModuleType)

def getattr_hierarchical(host: HostType, attr: str) -> Any:
    """
    Looks up and returns the given attribute on the host's hierarchy in the following order:

      1. Host variables
      2. Group variables (respecting topological order, excluding GroupType variables)
      3. Script variables (excluding ScriptType variables)
      4. raises AttributeError

    If the attribute starts with an underscore, the lookup will always be from the host object
    itself, and won't be propagated hierarchically. The same is True for any variable that
    is a module (so imported modules in group/script definitions will not be visible).

    Parameters
    ----------
    host
        The host for which the attribute should be retrieved.
    attr
        The attribute to retrieve.

    Returns
    -------
    Any
        The attribute's value if it was found.

    Raises
    ------
    AttributeError
        The given attribute was not found.
    """
    # While getattr implicitly does a local lookup before calling this function,
    # we still need this block to force certain variables to always be looked up locally.
    if attr.startswith("_") or attr in HostType.__annotations__:
        if attr not in vars(host):
            raise AttributeError(attr)
        return vars(host)[attr]

    if attr not in GroupType.__annotations__:
        # Look up variable on groups
        for g in G.group_order:
            # Only consider a group if the host is in that group
            if g not in vars(host)["groups"]:
                continue

            # Return the attribute if it is set on the group,
            # and if it is a normal variable
            group = G.groups[g]
            if hasattr(group, attr):
                value = getattr(group, attr)
                if _is_normal_var(attr, value):
                    return value

    if attr not in ScriptType.__annotations__:
        # Look up variable on current script
        # pylint: disable=protected-access,import-outside-toplevel,cyclic-import
        import fora.script
        if fora.script._this is not None:
            if hasattr(fora.script._this, attr):
                value = getattr(fora.script._this, attr)
                if _is_normal_var(attr, value):
                    return value

    raise AttributeError(attr)

def vars_hierarchical(host: HostType, include_all_host_variables: bool = False) -> dict[str, Any]:
    """
    Functions similarly to a hierarchical equivalent of `vars()`, just as
    `getattr_hierarchical` is the hierarchical equivalent of `getattr`.
    The same constraints as for `getattr_hierarchical` apply, but never raises
    an AttributeError.

    Parameters
    ----------
    host
        The host for which all variables should be collected.
    include_all_host_variables
        Whether to include all host variables that `var(host)` yields (also hidden and special variables such as __getattr__, or imported modules).

    Returns
    -------
    dict[str, Any]
        A dictionary containing all currently accessible variables.
    """
    # We will add variables from bottom-up so that low-priority
    # variables can be overwritten as expected.
    dvars = {}

    # First, add all variable from the current script
    # pylint: disable=protected-access,import-outside-toplevel,cyclic-import
    import fora.script
    if fora.script._this is not None:
        # Add variables from the script that are neither private
        # nor part of a script's standard variables (ScriptType.__annotations__)
        dvars.update({attr: v for attr,v in vars(fora.script._this).items() if _is_normal_var(attr, v) and attr not in ScriptType.__annotations__})

    # Add variable from groups (reverse order so that the highest-priority
    # group overwrites variables from lower priorities.
    for g in reversed(G.group_order):
        # Only consider a group if the host is in that group
        if g not in vars(host)["groups"]:
            continue

        # Add variables from groups that are neither private
        # nor part of a group's standard variables (GroupType.__annotations__)
        group = G.groups[g]
        dvars.update({attr: v for attr,v in vars(group).items() if _is_normal_var(attr, v) and attr not in GroupType.__annotations__})

    # Lastly add all host variables, as they have the highest priority.
    dvars.update({attr: v for attr,v in vars(host).items() if include_all_host_variables
        or (_is_normal_var(attr, v) and attr not in HostType.__annotations__)})
    return dvars

_this: HostType = cast(HostType, None) # Cast None to ease typechecking in user code.
"""
This variable holds all meta information available to a host module when
it is being loaded. It must not be used anywhere else but inside the
definition (source) of the actual module.
"""

current_host: HostType = cast(HostType, None) # Cast None to ease typechecking in user code.
"""The currently active host. Only set when a script is currently being executed on a host."""
