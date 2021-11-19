"""Provides API for group definitions."""

from __future__ import annotations
from types import ModuleType
from typing import cast

from fora import globals as G
from fora.types import GroupType

# TODO: add Raises to methods that raise errors
# TODO: replace ..code-block with smth else for pdoc3
# TODO: check all doc links and refactor them for pdoc3 (also maybe wrong links now)

def name() -> str:
    """
    Returns the name of the group that is currently being defined.

    Return
    ----------
    str
        The name of the group.
    """
    if _this is None:
        raise RuntimeError("This function may only be called inside a group module definition.")
    return _this.name

def before(group: str) -> None:
    """
    Adds a reverse-dependency on the given group.

    Parameters
    ----------
    group
        The group that must be loaded before this group.
    """
    if _this is None:
        raise RuntimeError("This function may only be called inside a group module definition.")
    if group not in G.available_groups:
        raise ValueError(f"Referenced invalid group '{group}'!")
    if group == _this.name:
        raise ValueError("Cannot add reverse-dependency to self!")

    # pylint: disable=protected-access
    _this._groups_before.add(group)

def before_all(groups: list[str]) -> None:
    """
    Adds a reverse-dependency on all given groups.

    Parameters
    ----------
    groups
        The groups
    """
    if _this is None:
        raise RuntimeError("This function may only be called inside a group module definition.")
    for g in groups:
        before(g)

def after(group: str) -> None:
    """
    Adds a dependency on the given group.

    Parameters
    ----------
    group
        The group that must be loaded after this group.
    """
    if _this is None:
        raise RuntimeError("This function may only be called inside a group module definition.")
    if group not in G.available_groups:
        raise ValueError(f"Referenced invalid group '{group}'!")
    if group == _this.name:
        raise ValueError("Cannot add dependency to self!")

    # pylint: disable=protected-access
    _this._groups_after.add(group)

def after_all(groups: list[str]) -> None:
    """
    Adds a dependency on all given groups.

    Parameters
    ----------
    groups
        The groups
    """
    if _this is None:
        raise RuntimeError("This function may only be called inside a group module definition.")
    for g in groups:
        after(g)

def get_variables(group: GroupType) -> set[str]:
    """
    Returns the list of all user-defined attributes for a group.

    Parameters
    ----------
    group
        The group module.

    Returns
    -------
    set[str]
        The user-defined attributes for the given group
    """
    module_vars = set(attr for attr in dir(group) if
                        not callable(getattr(group, attr)) and
                        not attr.startswith("_") and
                        not isinstance(getattr(group, attr), ModuleType))
    module_vars -= set(GroupType.__annotations__)
    return module_vars

_this: GroupType = cast(GroupType, None) # Cast None to ease typechecking in user code.
"""
This variable holds all meta information available to a group module when
it is being loaded. It must not be used anywhere else but inside the
definition (source) of the actual module.
"""
