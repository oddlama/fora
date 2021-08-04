"""
Provides the submodule loading functions.
"""

import glob
import inspect
import os
import sys
from itertools import combinations
from typing import cast

import simple_automation
from simple_automation.types import GroupType, HostType, InventoryType, ScriptType
from simple_automation.utils import die_error, print_error, load_py_module, rank_sort, CycleError
from simple_automation.connectors.connector import Connector

script_stack: list[tuple[ScriptType, inspect.FrameInfo]] = []
"""
A stack of all currently executed scripts ((name, file), frame).
"""

class DefaultGroup:
    """
    This class will be instanciated for the 'all' group, if it hasn't been defined externally.
    """

class DefaultHost:
    """
    This class will be instanciated for each host that has not been defined by a corresponding
    host module file, and is used to represent a host with no special configuration.
    """

    def __init__(self, name):
        self.url = name

def load_inventory(file: str) -> InventoryType:
    """
    Loads and validates the inventory definition from the given module file.

    Parameters
    ----------
    file : str
        The inventory module file to load

    Returns
    -------
    InventoryType
        The loaded group module
    """
    inventory = load_py_module(file)
    if not hasattr(inventory, 'hosts'):
        die_error("inventory must define a list of hosts!", loc="inventory.py")

    # Convert hosts to list to ensure list type
    inventory.hosts = list(inventory.hosts)
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
    meta = GroupType(name, module_file)

    # Normal groups have a dependency on the global 'all' group.
    if not name == 'all':
        meta.after("all")

    # Instanciate module
    with simple_automation.set_this(meta):
        ret = load_py_module(module_file)

    for reserved in GroupType.reserved_vars:
        if hasattr(ret, reserved):
            die_error(f"'{reserved}' is a reserved variable.", loc=meta.loaded_from)

    meta.transfer(ret)
    return ret

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
    conflicts = list(GroupType.get_variables(a) & GroupType.get_variables(b))
    had_conflicts = False
    for conflict in conflicts:
        if not had_conflicts:
            print_error("Found group variables with ambiguous evaluation order, insert group dependency or remove one definition.")
            had_conflicts = True
        print_error(f"Definition of '{conflict}' is in conflict with definition at '{b.loaded_from}", loc=a.loaded_from)
    return had_conflicts

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
        for before in groups[g].groups_before:
            groups[before].groups_after.add(g)

    # Deduplicate _after, clear before
    for _,group in groups.items():
        group.groups_before = set()
        group.groups_after = set(group.groups_after)

    # Recalculate _before from _after
    for g in groups:
        for after in groups[g].groups_after:
            groups[after].groups_before.add(g)

    # Deduplicate before
    for _,group in groups.items():
        group.groups_before = set(group.groups_before)

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
    l_before = lambda g: groups[g].groups_before
    l_after = lambda g: groups[g].groups_after

    try:
        gkeys = list(groups.keys())
        ranks_t = rank_sort(gkeys, l_before, l_after) # Top-down
        ranks_b = rank_sort(gkeys, l_after, l_before) # Bottom-up
    except CycleError as e:
        die_error(f"Dependency cycle detected! The cycle includes {[groups[g].loaded_from for g in e.cycle]}.")

    # Find cycles in dependencies by checking for the existence of any edge that doesn't increase the rank.
    # This is an error.
    for g in groups:
        for c in groups[g].groups_after:
            if ranks_t[c] <= ranks_t[g]:
                die_error(f"Dependency cycle detected! The cycle includes '{groups[g].loaded_from}' and '{groups[c].loaded_from}'.")

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

def define_special_global_variables(group_all):
    """
    Defines special global variables on the given all group.
    Respects if the corresponding variable is already set.
    """
    if not hasattr(group_all, 'simple_automation_managed'):
        setattr(group_all, 'simple_automation_managed', "This file is managed by simple automation.")

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
        loaded_groups[group.name] = cast(GroupType, group)

    # Create default all group if it wasn't defined
    if 'all' not in loaded_groups:
        default_group = cast(GroupType, DefaultGroup())
        setattr(default_group, 'meta', GroupType("all", "__internal__"))
        loaded_groups['all'] = default_group

    # Define special global variables
    gall = loaded_groups['all']
    define_special_global_variables(gall)

    # Firstly, deduplicate and unify each group's before and after dependencies,
    # and check for any self-dependencies.
    merge_group_dependencies(loaded_groups)

    # Find a topological order and check the groups for attribute conflicts.
    topological_order = sort_and_validate_groups(loaded_groups)

    return (loaded_groups, topological_order)

def resolve_connector(host: HostType):
    """
    Resolves the connector for a host, if it hasn't been set manually.
    We'll try to figure out which connector to use by detecting presence of their
    configuration options on the host module.

    Parameters
    ----------
    host: HostType
        The host
    """
    if host.connector is None:
        schema = host.url.split(':')[0]
        if schema in Connector.registered_connectors:
            host.connector = Connector.registered_connectors[schema]
        else:
            die_error(f"No connector found for schema {schema}", loc=host.loaded_from)
    elif callable(host.connector):
        # The connector was explicitly given
        pass
    else:
        die_error("Invalid connector was specified", loc=host.loaded_from)

def load_host(name: str, module_file: str) -> HostType:
    """
    Load and validates the host with the given name from the given module file path.

    Parameters
    ----------
    name: str
        The host name of the host to be loaded
    module_file: str
        The path to the host module file that will be instanciated

    Returns
    -------
    HostType
        The host module
    """
    module_file_exists = os.path.exists(module_file)
    meta = HostType(name, module_file if module_file_exists else "__internal__")
    meta.add_group("all")

    with simple_automation.set_this(meta):
        # Instanciate module
        if module_file_exists:
            ret = load_py_module(module_file)
        else:
            # Instanciate default module and set ssh_host to the name
            ret = cast(HostType, DefaultHost(name))

    # Check if the module did set any reserved variables
    for reserved in HostType.reserved_vars:
        if hasattr(ret, reserved):
            die_error(f"'{reserved}' is a reserved variable.", loc=meta.loaded_from)

    meta.transfer(ret)
    resolve_connector(ret)

    # Monkeypatch the __hasattr__ and __getattr__ methods to perform hierachical lookup from now on
    if module_file_exists:
        setattr(ret, '__getattr__', lambda attr: HostType.getattr_hierarchical(ret, attr))
        setattr(ret, '__hasattr__', lambda attr: HostType.hasattr_hierarchical(ret, attr))
    else:
        setattr(ret, '__getattr__', lambda s, attr: HostType.getattr_hierarchical(ret, attr))
        setattr(ret, '__hasattr__', lambda s, attr: HostType.hasattr_hierarchical(ret, attr))

    return ret

def load_hosts() -> dict[str, HostType]:
    """
    Loads all hosts defined in the inventory from their respective definition file in `./hosts/`.

    Returns
    -------
    dict[str, HostType]
        A mapping from name to host module
    """
    loaded_hosts = {}
    for host in simple_automation.inventory.hosts:
        if isinstance(host, str):
            loaded_hosts[host] = load_host(name=host, module_file=f"hosts/{host}.py")
        elif isinstance(host, tuple):
            (name, module_py) = host
            loaded_hosts[name] = load_host(name=name, module_file=module_py)
        else:
            die_error(f"invalid host '{str(host)}'", loc="inventory.py")
    return loaded_hosts

def load_site(inventories: list[str]):
    """
    Loads the whole site and exposes it globally via the corresponding variables
    in the simple_automation module.

    Parameters
    ----------
    inventories : list[str]
        A possibly mixed list of inventory definition files (e.g. inventory.py) and single
        host definitions in any ssh accepted syntax. The .py extension is used to disscern
        between these cases. If multiple python inventory modules are given, the first will
        become the main module stored in simple_automation.inventory, and the others will
        just have their hosts appended to the first module.
    """

    # Separate inventory modules from single host definitions
    module_files = []
    single_hosts = []
    for i in inventories:
        if i.endswith(".py"):
            module_files.append(i)
        else:
            single_hosts.append(i)

    # Load inventory module
    if len(module_files) == 0:
        # Use a default empty inventory
        simple_automation.inventory = InventoryType()
    else:
        # Load first inventory module file and append hosts from other inventory modules
        simple_automation.inventory = load_inventory(module_files[0])
        # Append hosts from other inventory modules
        for inv in module_files:
            simple_automation.inventory.hosts.extend(load_inventory(inv).hosts)

    # Append single hosts
    for shost in single_hosts:
        simple_automation.inventory.hosts.append(shost)

    # Load all groups from groups/*.py, then sort
    # groups respecting their declared dependencies
    simple_automation.groups, simple_automation.group_order = load_groups()

    # Load all hosts defined in the inventory
    simple_automation.hosts = load_hosts()

def run_script(script: str, frame: inspect.FrameInfo):
    """
    Loads and implicitly runs the given script by creating a new instance.

    Parameters
    ----------
    script : str
        The path to the script that should be instanciated
    frame
        The FrameInfo object as given by inspect.getouterframes(inspect.currentframe())[?]
        where the script call originates from. Used to keep track of the script invocation stack,
        which helps with debugging (e.g. cyclic script calls).
    """

    name = os.path.splitext(os.path.basename(script))[0]
    meta = ScriptType(name, script)

    script_stack.append((meta, frame))
    with simple_automation.set_this(meta):
        load_py_module(script)
    script_stack.pop()
