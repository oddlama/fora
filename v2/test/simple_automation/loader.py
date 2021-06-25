"""
Provides the submodule loading functions.
"""

import simple_automation
import glob
import os
from simple_automation.utils import die_error, load_py_module

def load_inventory():
    inventory = load_py_module('inventory.py')
    if not hasattr(inventory, 'hosts'):
        die_error("inventory.py: inventory must define a list of hosts!")
    if not isinstance(inventory.hosts, list):
        die_error("inventory.py: hosts variable must be a list!")
    return inventory

def load_group(module_file: str):
    ret = load_py_module(module_file)
    ret.name = os.path.splitext(os.path.basename(module_file))[0]
    ret.loaded_from = module_file

    # Dependent groups (before this)
    if not hasattr(ret, 'before'):
        ret.before = []
    if not isinstance(ret.before, list):
        die_error(f"{module_file}: 'before' must be a list!")

    # Dependent groups (after this)
    if not hasattr(ret, 'after'):
        ret.after = [] if ret.name == 'all' else ['all']
    if not isinstance(ret.after, list):
        die_error(f"{module_file}: 'after' must be a list!")

    return ret

def load_groups():
    # Load all groups defined in groups/*.py
    loaded_groups = {}
    for file in glob.glob('groups/*.py'):
        group = load_group(file)
        loaded_groups[group.name] = group

    # Create default all group if it wasn't defined
    if 'all' not in loaded_groups:
        # TODO instanciate default all module
        from simple_automation import default_group_all
        loaded_groups['all'] = default_group_all

    return loaded_groups

def rank_sort(vertices: list, preds_of, childs_of):
    # FIXME in description: must be cycle free already. Might detect cycle when
    # searching for root node, but this is not guaranteed to detect any cycle.

    # Create a mapping of vertices to ranks.
    ranks = {v: -1 for v in vertices}

    # While there is at least one node without a rank,
    # find the "tree root" of that portion of the graph and
    # assign ranks to all reachable children without ranks.
    while -1 in ranks.values():
        # Start at any unvisited node
        root = next(filter(lambda k: ranks[k] == -1, ranks.keys()))

        # Initialize a visited mapping to detect cycles
        visited = {v: False for v in vertices}
        visited[root] = True

        # Find the root of the current subtree,
        # or detect a cycle and abort.
        while len(preds_of(root)) > 0:
            root = preds_of(root)[0]
            if visited[root]:
                cycle_nodes = list(filter(lambda v: visited[v], vertices))
                raise ValueError(f"Cannot apply rank_sort to cyclic graph. Cycle includes: {cycle_nodes}")

            visited[root] = True

        # The root node has rank 0
        ranks[root] = 0

        # Now assign increasing ranks to children in a breadth-first manner
        # to avoid transitive dependencies from causing additional subtree-updates.
        # We start with a list of nodes to process and their parents stored as pairs.
        needs_rank_list = list([(c, root) for c in childs_of(root)])
        while len(needs_rank_list) > 0:
            # Take the next node to process
            n, p = needs_rank_list.pop(0)
            r = ranks[p] + 1

            # Skip nodes that already have a rank
            # higher than the one we would assign
            if ranks[n] >= r:
                continue

            # Assign rank
            ranks[n] = r
            # Queue childen for rank assignment
            needs_rank_list.extend([(c, n) for c in childs_of(n)])

    return ranks

def sort_groups(groups):
    # Check that all groups used in dependencies do exist.
    for _,group in groups.items():
        for g in group.before:
            if g not in groups:
                die_error(f"{group.loaded_from}: definition of before: Invalid group '{g}' or missing definition groups/{g}.py!")
        for g in group.after:
            if g not in groups:
                die_error(f"{group.loaded_from}: definition of after: Invalid group '{g}' or missing definition groups/{g}.py!")

    # Detect self-cycles
    for g,group in groups.items():
        if g in group.before:
            die_error(f"{group.loaded_from}: definition of before: Group '{g}' cannot depend on itself!")
        if g in group.after:
            die_error(f"{group.loaded_from}: definition of after: Group '{g}' cannot depend on itself!")

    # Unify before and after dependencies
    for g in groups:
        for before in groups[g].before:
            groups[before].after.append(g)

    # Deduplicate after, clear before
    for _,group in groups.items():
        group.before = []
        group.after = list(set(group.after))

    # Recalculate before from after
    for g in groups:
        for after in groups[g].after:
            groups[after].before.append(g)

    # Deduplicate before
    for _,group in groups.items():
        group.before = list(set(group.before))

    # TODO find strongly connected components. This is an error.

    # Rank sort from bottom-up and top-down to calculate minimum rank and maximum rank.
    # This is basically the earliest time a group might be applied (exactly after all dependencies
    # were processed), and the latest time (any other group requires this one to be processed first).
    #
    # Rank numbers are already 0-based. This means in the top-down view, the root node
    # has top-rank 0 and a high bottom-rank, and all leaves have bottom_rank 0 a high top-rank.
    l_before = lambda g: groups[g].before
    l_after = lambda g: groups[g].after
    ranks_t = rank_sort(groups.keys(), l_before, l_after) # Top-down
    ranks_b = rank_sort(groups.keys(), l_after, l_before) # Bottom-up

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
    for group in groups:
        for other in rank_intersections(group, ranks_min, ranks_max):
            # group shares at least one rank with other.
            pass

    for _,group in groups.items():
        group.after = list(set(group.after))
        print(f"{group.name}.after = {group.after}")
    for _,group in groups.items():
        print(f"{group.name}.before = {group.before}")

    # TODO ambiguity detection

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
