"""Provides the dynamic module loading utilities."""

import glob
import inspect
import os
import sys
from itertools import combinations
from types import ModuleType
from typing import Union, cast, Any, Optional

import fora.host
import fora.group
import fora.script

from fora import globals as G, logger
from fora.types import GroupType, HostType, InventoryType, ScriptType
from fora.utils import die_error, print_error, load_py_module, rank_sort, CycleError, set_this_group, set_this_host, set_this_script
from fora.connectors.connector import Connector

script_stack: list[tuple[ScriptType, inspect.FrameInfo]] = []
"""A stack of all currently executed scripts ((name, file), frame)."""

class DefaultGroup:
    """This class will be instanciated for the 'all' group, if it hasn't been defined externally."""

class DefaultHost:
    """
    This class will be instanciated for each host that has not been defined by a corresponding
    host module file, and is used to represent a host with no special configuration.
    """
    def __getattr__(self, attr: str) -> Any:
        return fora.host.getattr_hierarchical(cast(HostType, self), attr)

def load_inventory(file: str) -> InventoryType:
    """
    Loads and validates the inventory definition from the given module file.

    Parameters
    ----------
    file
        The inventory module file to load

    Returns
    -------
    InventoryType
        The loaded group module
    """
    inventory = cast(InventoryType, load_py_module(file))
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
    module_file
        The path to the file containing to the group definition

    Returns
    -------
    GroupType
        The loaded group module
    """

    name = os.path.splitext(os.path.basename(module_file))[0]
    meta = GroupType(name=name, _loaded_from=module_file)

    # Instanciate module
    with set_this_group(meta) as ctx:
        # Normal groups have a dependency on the global 'all' group.
        if not name == 'all':
            fora.group.after("all")

        def _pre_exec(module: ModuleType) -> None:
            meta.transfer(module)
            ctx.update(module)
        ret = cast(GroupType, load_py_module(module_file, pre_exec=_pre_exec))
    return ret

def check_modules_for_conflicts(a: GroupType, b: GroupType) -> bool:
    """
    Asserts that two modules don't contain conflicting attributes.
    Exits with an error in case any conflicts are detected.

    Parameters
    ----------
    a
        The first group module
    b
        The second group module

    Returns
    -------
    bool
        True when at least one conflicting attribute was found
    """
    # pylint: disable=protected-access
    conflicts = list(fora.group.get_variables(a) & fora.group.get_variables(b))
    had_conflicts = False
    for conflict in conflicts:
        if not had_conflicts:
            print_error("Found group variables with ambiguous evaluation order, insert group dependency or remove one definition.")
            had_conflicts = True
        print_error(f"Definition of '{conflict}' is in conflict with definition at '{b._loaded_from}", loc=a._loaded_from)
    return had_conflicts

def merge_group_dependencies(groups: dict[str, GroupType]) -> None:
    """
    Merges the dependencies of a group module.
    This means that before and after dependencies are duplicated to the referenced group,
    and duplicated afterwards. Any self-references are detected and will cause the program to exit
    with an error.

    Parameters
    ----------
    groups
        The dictionary of groups
    """
    # pylint: disable=protected-access
    # Unify _before and _after dependencies
    for g in groups:
        for before in groups[g]._groups_before:
            groups[before]._groups_after.add(g)

    # Deduplicate _after, clear before
    for _,group in groups.items():
        group._groups_before = set()
        group._groups_after = set(group._groups_after)

    # Recalculate _before from _after
    for g in groups:
        for after in groups[g]._groups_after:
            groups[after]._groups_before.add(g)

    # Deduplicate before
    for _,group in groups.items():
        group._groups_before = set(group._groups_before)

def sort_and_validate_groups(groups: dict[str, GroupType]) -> list[str]:
    """
    Topologically sorts a dictionary of group modules (indexed by name), by their declared dependencies.
    Also validates that the dependencies don't contain any cycles and don't contain any conflicting assignments.

    Parameters
    ----------
    groups
        The sorted dictionary of groups.

    Returns
    -------
    list[GroupType]
        The topologically sorted list of groups
    """
    # pylint: disable=protected-access

    # Rank sort from bottom-up and top-down to calculate minimum rank and maximum rank.
    # This is basically the earliest time a group might be applied (exactly after all dependencies
    # were processed), and the latest time (any other group requires this one to be processed first).
    #
    # Rank numbers are already 0-based. This means in the top-down view, the root node
    # has top-rank 0 and a high bottom-rank, and all leaves have bottom_rank 0 a high top-rank.
    l_before = lambda g: groups[g]._groups_before
    l_after = lambda g: groups[g]._groups_after

    try:
        gkeys = list(groups.keys())
        ranks_t = rank_sort(gkeys, l_before, l_after) # Top-down
        ranks_b = rank_sort(gkeys, l_after, l_before) # Bottom-up
    except CycleError as e:
        die_error(f"Dependency cycle detected! The cycle includes {[groups[g]._loaded_from for g in e.cycle]}.")

    # Find cycles in dependencies by checking for the existence of any edge that doesn't increase the rank.
    # This is an error.
    for g in groups:
        for c in groups[g]._groups_after:
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
        if G.args.debug:
            raise RuntimeError("Exiting because of group module conflicts.")
        sys.exit(1)

    # Return a topological order based on the top-rank
    return sorted(list(g for g in groups.keys()), key=lambda g: ranks_min[g])

def define_special_global_variables(group_all: GroupType) -> None:
    """
    Defines special global variables on the given all group.
    Respects if the corresponding variable is already set.
    """
    if not hasattr(group_all, 'fora_managed'):
        setattr(group_all, 'fora_managed', "This file is managed by fora.")

def load_groups() -> tuple[dict[str, GroupType], list[str]]:
    """
    Loads all groups from their definition files in `./groups/`,
    validates their dependencies and returns the groups and a topological
    order respecting the dependency declarations.

    Parameters
    ----------
    groups
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

    if 'all' not in available_groups:
        available_groups.append('all')

    # Store available_groups so it can be accessed while groups are actually loaded.
    G.available_groups = available_groups

    # Load all groups defined in groups/*.py
    loaded_groups = {}
    for file in group_files:
        group = load_group(file)
        loaded_groups[group.name] = group

    # Create default all group if it wasn't defined
    if 'all' not in loaded_groups:
        default_group = cast(GroupType, DefaultGroup())
        GroupType(name="all", _loaded_from="__all__internal_group__").transfer(default_group)
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

def resolve_connector(host: HostType) -> None:
    """
    Resolves the connector for a host, if it hasn't been set manually.
    We'll try to figure out which connector to use by detecting presence of their
    configuration options on the host module.

    Parameters
    ----------
    host
        The host
    """
    # pylint: disable=protected-access
    if host.connector is None:
        if ':' not in host.url:
            die_error("Url doesn't include a schema and no connector was specified explicitly", loc=host._loaded_from)
        schema = host.url.split(':')[0]
        if schema in Connector.registered_connectors:
            host.connector = Connector.registered_connectors[schema]
        else:
            die_error(f"No connector found for schema {schema}", loc=host._loaded_from)

def load_host(name: str, module_file: Optional[str] = None) -> HostType:
    """
    Load and validates the host with the given name from the given module file path.

    Parameters
    ----------
    name
        The host name of the host to be loaded
    module_file
        The path to the host module file that will be instanciated.
        Pass None to try loading `hosts/{name}.py` and otherwise fall
        back to instanciating a `DefaultHost` if the name is an url scheme `(*:*)`.

    Returns
    -------
    HostType
        The host module
    """
    requires_module_file = module_file is not None
    if module_file is None:
        module_file = f"hosts/{name}.py"

    module_file_exists = os.path.exists(module_file)
    url = name if ':' in name else f"ssh://{name}"
    meta = HostType(name=name, _loaded_from=module_file if module_file_exists else "__cmdline__", url=url)

    with set_this_host(meta) as ctx:
        fora.host.add_group("all")

        # Instanciate module
        if module_file_exists:
            def _pre_exec(module: ModuleType) -> None:
                meta.transfer(module)
                ctx.update(module)
            ret = cast(HostType, load_py_module(module_file, pre_exec=_pre_exec))
            setattr(ret, '__getattr__', lambda attr, ret=ret: fora.host.getattr_hierarchical(ret, attr))
        else:
            if requires_module_file:
                raise ValueError(f"module file '{module_file}' for host '{name}' doesn't exist")
            # Instanciate default module
            ret = cast(HostType, DefaultHost())
            meta.transfer(ret)

    resolve_connector(ret)
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
    for host in G.inventory.hosts:
        if isinstance(host, str):
            if host in loaded_hosts:
                raise ValueError(f"duplicate host: {host}")
            loaded_hosts[host] = load_host(name=host)
        elif isinstance(host, tuple):
            (name, module_py) = host
            if name in loaded_hosts:
                raise ValueError(f"duplicate host: {host}")
            loaded_hosts[name] = load_host(name=name, module_file=module_py)
        else:
            die_error(f"invalid host '{str(host)}'", loc="inventory.py") # type: ignore[unreachable]
    return loaded_hosts

def load_site(inventories: list[Union[str, tuple[str, str]]]) -> None:
    """
    Loads the whole site and exposes it globally via the corresponding variables
    in the fora module.

    Parameters
    ----------
    inventories
        A possibly mixed list of inventory definition files (e.g. inventory.py) and single
        host definitions in any ssh accepted syntax. The .py extension is used to disscern
        between these cases. If multiple python inventory modules are given, the first will
        become the main module stored in fora.inventory, and the others will
        just have their hosts appended to the first module.
    """

    # Separate inventory modules from single host definitions
    module_files: list[str] = []
    single_hosts: list[Union[str, tuple[str, str]]] = []
    for i in inventories:
        if isinstance(i, str) and i.endswith(".py"):
            module_files.append(i)
        else:
            single_hosts.append(i)

    # Load inventory module
    if len(module_files) == 0:
        # Use a default empty inventory
        G.inventory = InventoryType()
    else:
        # Load first inventory module file and append hosts from other inventory modules
        G.inventory = load_inventory(module_files[0])
        # Append hosts from other inventory modules
        for inv in module_files[1:]:
            G.inventory.hosts.extend(load_inventory(inv).hosts)

    # Append single hosts
    for shost in single_hosts:
        G.inventory.hosts.append(shost)

    # Load all groups from groups/*.py, then sort
    # groups respecting their declared dependencies
    G.groups, G.group_order = load_groups()

    # Load all hosts defined in the inventory
    G.hosts = load_hosts()

def run_script(script: str,
               frame: inspect.FrameInfo,
               params: Optional[dict[str, Any]] = None,
               name: Optional[str] = None) -> None:
    """
    Loads and implicitly runs the given script by creating a new instance.

    Parameters
    ----------
    script
        The path to the script that should be instanciated
    frame
        The FrameInfo object as given by inspect.getouterframes(inspect.currentframe())[?]
        where the script call originates from. Used to keep track of the script invocation stack,
        which helps with debugging (e.g. cyclic script calls).
    name
        A printable name for the script. Defaults to the script path.
    """

    # It is intended that the name is passed before resolving it, so
    # that it is None if the user didn't pass one specifically.
    logger.run_script(script, name=name)

    with logger.indent():
        if name is None:
            name = os.path.splitext(os.path.basename(script))[0]

        meta = ScriptType(name, script)
        script_stack.append((meta, frame))
        try:
            with set_this_script(meta) as ctx:
                # New script instance starts with fresh set of default values.
                # Use defaults() here to start with the connections base settings.
                with fora.script.defaults():
                    def _pre_exec(module: ModuleType) -> None:
                        meta.transfer(module)
                        ctx.update(module)
                        setattr(module, '_params', params or {})
                    load_py_module(script, pre_exec=_pre_exec)
        except Exception as e:
            # Save the current script_stack in any exception thrown from this context
            # for later use in any exception handler.
            if not hasattr(e, 'script_stack'):
                setattr(e, 'script_stack', script_stack.copy())
            raise
        finally:
            script_stack.pop()
