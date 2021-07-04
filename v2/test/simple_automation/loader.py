"""
Provides the submodule loading functions.
"""

import glob
import os
import sys
from itertools import combinations
from typing import cast

import simple_automation
import simple_automation.host
import simple_automation.group

from simple_automation.utils import die_error, print_error, load_py_module, rank_sort, CycleError
from simple_automation.types import GroupType, HostType, InventoryType

def load_inventory() -> InventoryType:
    """
    Loads and validates the inventory definition from ./inventory.py.

    Returns
    -------
    InventoryType
        The loaded group module
    """
    inventory = load_py_module('inventory.py')
    if not hasattr(inventory, 'hosts'):
        die_error("inventory.py: inventory must define a list of hosts!")
    if not isinstance(inventory.hosts, list):
        die_error("inventory.py: hosts variable must be a list!")
    return inventory

def load_group(module_file: str) -> GroupType:
    """
    Loads and validates a group definition from the given file.

    Parameters
    ----------
    module_file : str
        The path to the file containing to the group definition

    Returns
    -------
    GroupType
        The loaded group module
    """

    name = os.path.splitext(os.path.basename(module_file))[0]
    meta = simple_automation.group.GroupMeta(name, module_file)

    # Normal groups have a dependency on the global 'all' group.
    if not name == 'all':
        meta.after("all")

    # Instanciate module
    simple_automation.group.this = meta
    ret = load_py_module(module_file)
    simple_automation.group.this = None

    ret.meta = meta
    return ret

def get_group_variables(group: GroupType) -> set[str]:
    """
    Returns the list of all user-defined attributes for a group.

    Parameters
    ----------
    group : GroupType
        The group module

    Returns
    -------
    set[str]
        The user-defined attributes for the given group
    """
    return set(attr for attr in dir(group) if not callable(getattr(group, attr)) and not attr.startswith("_"))

def check_modules_for_conflicts(a: GroupType, b: GroupType) -> bool:
    """
    Asserts that two modules don't contain conflicting attributes.
    Exits with an error in case any conflicts are detected.

    Parameters
    ----------
    a : GroupType
        The first group module
    b : GroupType
        The second group module

    Returns
    -------
    bool
        True when at least one conflicting attribute was found
    """
    conflicts = list(get_group_variables(a) & get_group_variables(b))
    for conflict in conflicts:
        print_error(f"'{a.meta.loaded_from}': Definition of '{conflict}' is in conflict with definition at '{b.meta.loaded_from}'. (Group order is ambiguous, insert dependency or remove one definition.)")
    return len(conflicts) > 0

def merge_group_dependencies(groups: dict[str, GroupType]):
    """
    Merges the dependencies of a group module.
    This means that before and after dependencies are duplicated to the referenced group,
    and duplicated afterwards. Any self-references are detected and will cause the program to exit
    with an error.

    Parameters
    ----------
    groups : dict[str, GroupType]
        The dictionary of groups
    """
    # Unify _before and _after dependencies
    for g in groups:
        for before in groups[g].meta.groups_before:
            groups[before].meta.groups_after.add(g)

    # Deduplicate _after, clear before
    for _,group in groups.items():
        group.meta.groups_before = set()
        group.meta.groups_after = set(group.meta.groups_after)

    # Recalculate _before from _after
    for g in groups:
        for after in groups[g].meta.groups_after:
            groups[after].meta.groups_before.add(g)

    # Deduplicate before
    for _,group in groups.items():
        group.meta.groups_before = set(group.meta.groups_before)

def sort_and_validate_groups(groups: dict[str, GroupType]) -> list[str]:
    """
    Topologically sorts a dictionary of group modules (indexed by name), by their declared dependencies.
    Also validates that the dependencies don't contain any cycles and don't contain any conflicting assignments.

    Parameters
    ----------
    groups : dict[str, GroupType]
        The sorted dictionary of groups.

    Returns
    -------
    list[GroupType]
        The topologically sorted list of groups
    """

    # Rank sort from bottom-up and top-down to calculate minimum rank and maximum rank.
    # This is basically the earliest time a group might be applied (exactly after all dependencies
    # were processed), and the latest time (any other group requires this one to be processed first).
    #
    # Rank numbers are already 0-based. This means in the top-down view, the root node
    # has top-rank 0 and a high bottom-rank, and all leaves have bottom_rank 0 a high top-rank.
    l_before = lambda g: groups[g].meta.groups_before
    l_after = lambda g: groups[g].meta.groups_after

    try:
        gkeys = list(groups.keys())
        ranks_t = rank_sort(gkeys, l_before, l_after) # Top-down
        ranks_b = rank_sort(gkeys, l_after, l_before) # Bottom-up
    except CycleError as e:
        die_error(f"Dependency cycle detected! The cycle includes {[groups[g].meta.loaded_from for g in e.cycle]}.")

    # Find cycles in dependencies by checking for the existence of any edge that doesn't increase the rank.
    # This is an error.
    for g in groups:
        for c in groups[g].meta.groups_after:
            if ranks_t[c] <= ranks_t[g]:
                die_error(f"Dependency cycle detected! The cycle includes '{groups[g].meta.loaded_from}' and '{groups[c].meta.loaded_from}'.")

    # Find the maximum rank. Both ranking systems have the same number of ranks. This is
    # true because the longest dependency chain determines the amount of ranks, and all dependencies
    # are the same.
    ranks_t_max = max(ranks_t.values())
    ranks_b_max = max(ranks_b.values())
    assert ranks_t_max == ranks_b_max
    n_ranks = ranks_b_max

    # Rebase bottom-ranks on top-ranks. We now want to transform top-ranks into minimum-ranks and
    # bottom-ranks into maximum-ranks, as viewed from a top-down scheme. I.e. we want to know the
    # range of ranks a module could occupy in any valid topological order. Therefore, we will simply
    # subtract all bottom-ranks from the highest rank number to get maximum-ranks. The top-down ranks
    # are already the minimum ranks.
    ranks_min = ranks_t
    ranks_max = {k: n_ranks - v for k,v in ranks_b.items()}

    # For each group find all other groups that share at lease one rank. This means
    # that there exists a topological order where A comes before B as well as a topological order where
    # this order is reversed. These pairs will then be tested for any variable that is assigned in both.
    # This would be an error, as the order of assignment and therfore the final value is ambiguous.
    # Although these kind of errors are not fatal, we collect all and exit if necessary,
    # because this constitutes a group design issue and should be fixed.
    has_conflicts = False
    for a, b in combinations(groups, 2):
        # Skip pair if the ranks don't overlap
        if ranks_max[a] < ranks_min[b] or ranks_min[a] > ranks_max[b]:
            continue

        # The two groups a and b share at least one rank with other,
        # so we need to make sure they can't conflict
        has_conflicts |= check_modules_for_conflicts(groups[a], groups[b])

    if has_conflicts:
        sys.exit(1)

    # Return a topological order based on the top-rank
    return sorted(list(g for g in groups.keys()), key=lambda g: ranks_min[g])

def load_groups() -> tuple[dict[str, GroupType], list[str]]:
    """
    Loads all groups from their definition files in `./groups/`,
    validates their dependencies and returns the groups and a topological
    order respecting the dependency declarations.

    Parameters
    ----------
    groups : dict[str, GroupType]
        The sorted dictionary of groups.

    Returns
    -------
    tuple[dict[str, GroupType], list[str]]
        A dictionary of all loaded group modules index by their name, and a valid topological order
    """
    # Pre-load available group names
    group_files = list(glob.glob('groups/*.py'))
    available_groups = []
    for file in group_files:
        available_groups.append(os.path.splitext(os.path.basename(file))[0])

    # Store available_groups so it can be accessed while groups are actually loaded.
    simple_automation.available_groups = available_groups

    # Load all groups defined in groups/*.py
    loaded_groups = {}
    for file in group_files:
        group = load_group(file)
        loaded_groups[group.meta.name] = cast(GroupType, group)

    # Create default all group if it wasn't defined
    if 'all' not in loaded_groups:
        # pylint: disable=import-outside-toplevel
        from simple_automation import default_group_all
        loaded_groups['all'] = cast(GroupType, default_group_all)

    # Firstly, deduplicate and unify each group's before and after dependencies,
    # and check for any self-dependencies.
    merge_group_dependencies(loaded_groups)

    # Find a topological order and check the groups for attribute conflicts.
    topological_order = sort_and_validate_groups(loaded_groups)

    return (loaded_groups, topological_order)

def load_host(host_id: str, module_file: str) -> HostType:
    """
    Load and validates the host with the given id from the given module file path.

    Parameters
    ----------
    host_id: str
        The host id of the host to be loaded
    module_file: str
        The path to the host module file that will be instanciated

    Returns
    -------
    HostType
        The host module
    """
    meta = simple_automation.host.HostMeta(host_id, module_file)
    meta.add_group("all")

    # Instanciate module
    simple_automation.host.this = meta
    ret = load_py_module(module_file)
    simple_automation.host.this = None

    ret.meta = meta
    return ret

def load_hosts() -> list[HostType]:
    """
    Loads all hosts defined in the inventory from their respective definition file in `./hosts/`.

    Returns
    -------
    list[HostType]
        A list of the loaded hosts
    """
    loaded_hosts = []
    for host in simple_automation.inventory.hosts:
        if isinstance(host, str):
            loaded_hosts.append(load_host(host_id=host, module_file=f"hosts/{host}.py"))
        elif isinstance(host, tuple):
            (host_id, module_py) = host
            loaded_hosts.append(load_host(host_id=host_id, module_file=module_py))
        else:
            die_error(f"inventory.py: invalid host '{str(host)}'")
    return loaded_hosts

def load_site():
    """
    Loads the whole site and exposes it globally via the corresponding variables
    in the simple_automation module.
    """
    # Load the inventory
    simple_automation.inventory = load_inventory()

    # Load all groups from groups/*.py, then sort
    # groups respecting their declared dependencies
    simple_automation.groups, simple_automation.group_order = load_groups()

    # Load all hosts defined in the inventory
    simple_automation.hosts = load_hosts()
