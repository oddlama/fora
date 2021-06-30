"""
Provides the submodule loading functions.
"""

# Disable protected access warnings, because this is intended for this module.
# pylint: disable=protected-access

import glob
import os
import sys
from itertools import combinations
from types import ModuleType

import simple_automation
from simple_automation.utils import die_error, print_error, load_py_module, rank_sort

def load_inventory() -> ModuleType:
    """
    Loads and validates the inventory definition from ./inventory.py.

    Returns
    -------
    ModuleType
        The loaded group module
    """
    inventory = load_py_module('inventory.py')
    if not hasattr(inventory, 'hosts'):
        die_error("inventory.py: inventory must define a list of hosts!")
    if not isinstance(inventory.hosts, list):
        die_error("inventory.py: hosts variable must be a list!")
    return inventory

def load_group(module_file: str) -> ModuleType:
    """
    Loads and validates a group definition from the given file.

    Parameters
    ----------
    module_file : str
        The path to the file containing to the group definition

    Returns
    -------
    ModuleType
        The loaded group module
    """
    ret = load_py_module(module_file)
    ret._name = os.path.splitext(os.path.basename(module_file))[0]
    ret._loaded_from = module_file

    # Dependent groups (before this)
    if not hasattr(ret, '_before'):
        ret._before = []
    if not isinstance(ret._before, list):
        die_error(f"{module_file}: '_before' must be a list!")

    # Dependent groups (after this)
    if not hasattr(ret, '_after'):
        ret._after = [] if ret._name == 'all' else ['all']
    if not isinstance(ret._after, list):
        die_error(f"{module_file}: '_after' must be a list!")

    return ret

def get_group_variables(group: ModuleType) -> set[str]:
    """
    Returns the list of all user-defined attributes for a group.

    Parameters
    ----------
    group : ModuleType
        The group module

    Returns
    -------
    set[str]
        The user-defined attributes for the given group
    """
    return set(attr for attr in dir(group) if not callable(getattr(group, attr)) and not attr.startswith("_"))

def check_modules_for_conflicts(a: ModuleType, b: ModuleType) -> bool:
    """
    Asserts that two modules don't contain conflicting attributes.
    Exits with an error in case any conflicts are detected.

    Parameters
    ----------
    a : ModuleType
        The first group module
    b : ModuleType
        The second group module

    Returns
    -------
    bool
        True when at least one conflicting attribute was found
    """
    conflicts = list(get_group_variables(a) & get_group_variables(b))
    for conflict in conflicts:
        print_error(f"'{a._loaded_from}': Definition of '{conflict}' is in conflict with definition at '{b._loaded_from}'. (Group order is ambiguous, insert dependency or remove one definition.)")
    return len(conflicts) > 0

def merge_group_dependencies(groups: dict[str, ModuleType]):
    """
    Merges the dependencies of a group module.
    This means that before and after dependencies are duplicated to the referenced group,
    and duplicated afterwards. Any self-references are detected and will cause the program to exit
    with an error.

    Parameters
    ----------
    groups : dict[str, ModuleType]
        The dictionary of groups
    """
    # pylint: disable=too-many-branches
    # Check that all groups used in dependencies do actually exist.
    for _,group in groups.items():
        for g in group._before:
            if g not in groups:
                die_error(f"{group._loaded_from}: definition of _before: Invalid group '{g}' or missing definition groups/{g}.py!")
        for g in group._after:
            if g not in groups:
                die_error(f"{group._loaded_from}: definition of _after: Invalid group '{g}' or missing definition groups/{g}.py!")

    # Detect self-cycles
    for g,group in groups.items():
        if g in group._before:
            die_error(f"{group._loaded_from}: definition of _before: Group '{g}' cannot depend on itself!")
        if g in group._after:
            die_error(f"{group._loaded_from}: definition of _after: Group '{g}' cannot depend on itself!")

    # Unify _before and _after dependencies
    for g in groups:
        for before in groups[g]._before:
            groups[before]._after.append(g)

    # Deduplicate _after, clear before
    for _,group in groups.items():
        group._before = []
        group._after = list(set(group._after))

    # Recalculate _before from _after
    for g in groups:
        for after in groups[g]._after:
            groups[after]._before.append(g)

    # Deduplicate before
    for _,group in groups.items():
        group._before = list(set(group._before))

def sort_and_validate_groups(groups: dict[str, ModuleType]) -> list[str]:
    """
    Topologically sorts a dictionary of group modules (indexed by name), by their declared dependencies.
    Also validates that the dependencies don't contain any cycles and don't contain any conflicting assignments.

    Parameters
    ----------
    groups : dict[str, ModuleType]
        The sorted dictionary of groups.

    Returns
    -------
    list[ModuleType]
        The topologically sorted list of groups
    """

    # Rank sort from bottom-up and top-down to calculate minimum rank and maximum rank.
    # This is basically the earliest time a group might be applied (exactly after all dependencies
    # were processed), and the latest time (any other group requires this one to be processed first).
    #
    # Rank numbers are already 0-based. This means in the top-down view, the root node
    # has top-rank 0 and a high bottom-rank, and all leaves have bottom_rank 0 a high top-rank.
    l_before = lambda g: groups[g]._before
    l_after = lambda g: groups[g]._after

    try:
        gkeys = list(groups.keys())
        ranks_t = rank_sort(gkeys, l_before, l_after) # Top-down
        ranks_b = rank_sort(gkeys, l_after, l_before) # Bottom-up
    except ValueError as e:
        die_error(f"Dependency cycle detected! The cycle includes {[groups[g]._loaded_from for g in e.cycle]}.")

    # Find cycles in dependencies by checking for the existence of any edge that doesn't increase the rank.
    # This is an error.
    for g in groups:
        for c in groups[g]._after:
            if ranks_t[c] <= ranks_t[g]:
                die_error(f"Dependency cycle detected! The cycle includes '{groups[g]._loaded_from}' and '{groups[c]._loaded_from}'.")

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

def load_groups() -> tuple[dict[str, ModuleType], list[str]]:
    """
    Loads all groups from their definition files in `./groups/`,
    validates their dependencies and returns the groups and a topological
    order respecting the dependency declarations.

    Parameters
    ----------
    groups : dict[str, ModuleType]
        The sorted dictionary of groups.

    Returns
    -------
    tuple[dict[str, ModuleType], list[str]]
        A dictionary of all loaded group modules index by their name, and a valid topological order
    """
    # Load all groups defined in groups/*.py
    loaded_groups = {}
    for file in glob.glob('groups/*.py'):
        group = load_group(file)
        loaded_groups[group._name] = group

    # Create default all group if it wasn't defined
    if 'all' not in loaded_groups:
        # pylint: disable=import-outside-toplevel
        from simple_automation import default_group_all
        loaded_groups['all'] = default_group_all

    # Firstly, deduplicate and unify each group's before and after dependencies,
    # and check for any self-dependencies.
    merge_group_dependencies(loaded_groups)

    # Find a topological order and check the groups for attribute conflicts.
    topological_order = sort_and_validate_groups(loaded_groups)

    return (loaded_groups, topological_order)

def load_host(host_id: str, module_file: str) -> ModuleType:
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
    ModuleType
        The host module
    """
    simple_automation.host_id = host_id
    ret = load_py_module(module_file)
    simple_automation.host_id = None

    ret.id = host_id
    if not hasattr(ret, 'ssh_host'):
        die_error(f"{module_file}: ssh_host not defined!")
    if not hasattr(ret, 'groups'):
        ret.groups = []
    else:
        for group in ret.groups:
            if group not in simple_automation.groups:
                die_error(f"{module_file}: Invalid group '{group}' or missing definition groups/{group}.py!")

    # Add all hosts to the group "all", and deduplicate the groups list.
    ret.groups = list(set(ret.groups + ["all"]))

    return ret

def load_hosts() -> list[ModuleType]:
    """
    Loads all hosts defined in the inventory from their respective definition file in `./hosts/`.

    Returns
    -------
    list[ModuleType]
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

def load_task(module_file: str) -> ModuleType:
    """
    Load and validates a task from the given module file path.

    Parameters
    ----------
    module_file: str
        The path to the task module file that will be instanciated

    Returns
    -------
    ModuleType
        The task module
    """
    ret = load_py_module(module_file)
    ret._name = os.path.splitext(os.path.basename(module_file))[0]
    ret._loaded_from = module_file
    return ret

def load_tasks() -> dict[str, ModuleType]:
    """
    Loads all tasks defined either by single-file modules as `./tasks/*.py` or by directory modules
    as `./tasks/*/__init__.py`.

    Returns
    -------
    list[ModuleType]
        A list of the loaded tasks
    """
    # Load all tasks defined as single-file modules (tasks/*.py) or module directories (tasks/*/__init__.py)
    loaded_tasks = {}
    for file in glob.glob('tasks/*.py'):
        task = load_task(file)
        loaded_tasks[task._name] = task

    # TODO module directory tasks

    return loaded_tasks

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

    # Load all tasks from tasks/
    simple_automation.tasks = load_tasks()
