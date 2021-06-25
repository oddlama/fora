"""
Provides the submodule loading functions.
"""

import simple_automation
import glob
import os
import sys
from itertools import combinations
from simple_automation.utils import die_error, print_error, load_py_module, rank_sort

def load_inventory():
    inventory = load_py_module('inventory.py')
    if not hasattr(inventory, 'hosts'):
        die_error("inventory.py: inventory must define a list of hosts!")
    if not isinstance(inventory.hosts, list):
        die_error("inventory.py: hosts variable must be a list!")
    return inventory

def load_group(module_file: str):
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

def load_groups():
    # Load all groups defined in groups/*.py
    loaded_groups = {}
    for file in glob.glob('groups/*.py'):
        group = load_group(file)
        loaded_groups[group._name] = group

    # Create default all group if it wasn't defined
    if 'all' not in loaded_groups:
        # TODO instanciate default all module
        from simple_automation import default_group_all
        loaded_groups['all'] = default_group_all

    return loaded_groups

def check_modules_for_conflicts(a, b):
    get_attrs = lambda x: set([attr for attr in dir(x) if not callable(getattr(x, attr)) and not attr.startswith("_")])
    conflicts = list(get_attrs(a) & get_attrs(b))
    for conflict in conflicts:
        print_error(f"'{a._loaded_from}': Definition of '{conflict}' is in conflict with definition at '{b._loaded_from}'. (Group order is ambiguous, insert dependency or remove one definition.)")
    return len(conflicts) > 0

def sort_groups(groups):
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

    # Rank sort from bottom-up and top-down to calculate minimum rank and maximum rank.
    # This is basically the earliest time a group might be applied (exactly after all dependencies
    # were processed), and the latest time (any other group requires this one to be processed first).
    #
    # Rank numbers are already 0-based. This means in the top-down view, the root node
    # has top-rank 0 and a high bottom-rank, and all leaves have bottom_rank 0 a high top-rank.
    l_before = lambda g: groups[g]._before
    l_after = lambda g: groups[g]._after

    try:
        ranks_t = rank_sort(groups.keys(), l_before, l_after) # Top-down
        ranks_b = rank_sort(groups.keys(), l_after, l_before) # Bottom-up
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

    return groups

def load_host(host_id: str, module_file: str):
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

def load_hosts():
    # Load all hosts defined in the inventory
    loaded_hosts = []
    for host in simple_automation.inventory.hosts:
        if isinstance(host, str):
            loaded_hosts.append(load_host(host_id=host, module_file=f"hosts/{host}.py"))
        elif isinstance(host, tuple):
            (name, module_py) = host
            loaded_hosts.append(load_host(name=name, module_file=module_py))
        else:
            die_error(f"inventory.py: invalid host '{str(host)}'")
    return loaded_hosts

def load_tasks():
    return None

def load_site():
    # Load the inventory
    simple_automation.inventory = load_inventory()

    # Load all groups from groups/*.py, then sort
    # groups respecting their declared dependencies
    simple_automation.groups = sort_groups(load_groups())

    # Load all hosts defined in the inventory
    simple_automation.hosts = load_hosts()

    # Load all tasks recursively from tasks/
    simple_automation.tasks = load_tasks()
