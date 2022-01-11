"""Provides the dynamic module loading utilities."""

import inspect
import os
import sys
from itertools import combinations
from types import ModuleType
from typing import Union, cast, Any, Optional

import fora.host
import fora.script

from fora import globals as G, logger
from fora.types import GroupWrapper, HostType, ScriptType
from fora.utils import FatalError, print_error, load_py_module, rank_sort, CycleError, set_this_host, set_this_script
from fora.connectors.connector import Connector

script_stack: list[tuple[ScriptType, inspect.FrameInfo]] = []
"""A stack of all currently executed scripts ((name, file), frame)."""

class DefaultGroup:
    """This class will be instanciated for empty groups without associated module files."""

class DefaultHost:
    """
    This class will be instanciated for each host that has not been defined by a corresponding
    host module file, and is used to represent a host with no special configuration.
    """
    def __getattr__(self, attr: str) -> Any:
        return fora.host.getattr_hierarchical(cast(HostType, self), attr)

class ImmediateInventory:
    """A temporary inventory just for a single run, without the ability to load host or group module files."""
    def __init__(self, hosts: list[Union[str, tuple[str, str]]]) -> None:
        self.hosts = list(hosts)

    @staticmethod
    def base_dir(inventory: Any) -> str:
        """An immediate inventory has no base directory."""
        _ = (inventory)
        raise RuntimeError("Immediate inventories have no base directory!")

    @staticmethod
    def group_module_file(inventory: Any, name: str) -> Optional[str]:
        _ = (inventory, name)
        return None

    @staticmethod
    def host_module_file(inventory: Any, name: str) -> Optional[str]:
        _ = (inventory, name)
        return None

    @staticmethod
    def available_groups(inventory: Any) -> set[str]:
        """An immediate inventory has no groups."""
        _ = (inventory)
        return set()

def load_inventory(file: str) -> ModuleType:
    """
    Loads and validates the inventory definition from the given module file.

    Parameters
    ----------
    file
        The inventory module file to load

    Returns
    -------
    ModuleType
        The loaded inventory module

    Raises
    ------
    FatalError
        The loaded inventory was invalid.
    """
    inventory = load_py_module(file)

    # Check that the hosts definition is valid.
    if not hasattr(inventory, 'hosts'):
        raise FatalError("inventory must define a list of hosts!", loc=file)
    hosts = getattr(inventory, "hosts")
    if not isinstance(hosts, list):
        raise FatalError(f"inventory.hosts must be of type list, not {type(hosts)}!", loc=file)

    return inventory

def load_group(wrapper: GroupWrapper, module_file: str) -> None:
    """
    Loads and validates a group definition from the given file.

    Parameters
    ----------
    wrapper
        The wrapper to wrap the loaded module in.
    module_file
        The path to the file containing to the group definition
    """
    # Instanciate module
    def _pre_exec(module: ModuleType) -> None:
        G.group = wrapper
        wrapper.wrap(module, copy_members=True, copy_functions=True)

        # Normal groups always have a dependency on the global 'all' group.
        if not wrapper.name == "all":
            wrapper.after("all")

    load_py_module(module_file, pre_exec=_pre_exec)
    G.group = cast(GroupWrapper, None)

def get_group_variables(group: GroupWrapper) -> set[str]:
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
    module_vars -= set(GroupWrapper.__annotations__)
    return module_vars

def check_modules_for_conflicts(a: GroupWrapper, b: GroupWrapper) -> bool:
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
    conflicts = list(get_group_variables(a) & get_group_variables(b))
    had_conflicts = False
    for conflict in conflicts:
        if not had_conflicts:
            print_error("Found group variables with ambiguous evaluation order, insert group dependency or remove one definition.")
            had_conflicts = True
        print_error(f"Definition of '{conflict}' is in conflict with definition at '{b._loaded_from}", loc=a._loaded_from)
    return had_conflicts

def merge_group_dependencies(groups: dict[str, GroupWrapper]) -> None:
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

def sort_and_validate_groups(groups: dict[str, GroupWrapper]) -> list[str]:
    """
    Topologically sorts a dictionary of group modules (indexed by name), by their declared dependencies.
    Also validates that the dependencies don't contain any cycles and don't contain any conflicting assignments.

    Parameters
    ----------
    groups
        The sorted dictionary of groups.

    Returns
    -------
    list[GroupWrapper]
        The topologically sorted list of groups

    Raises
    ------
    ValueError
        The loaded inventory was invalid.
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
        raise ValueError(f"dependency cycle detected! The cycle includes {[groups[g]._loaded_from for g in e.cycle]}.") from None

    # Find cycles in dependencies by checking for the existence of any edge that doesn't increase the rank.
    # This is an error.
    for g in groups:
        for c in groups[g]._groups_after:
            if ranks_t[c] <= ranks_t[g]:
                raise ValueError(f"dependency cycle detected! The cycle includes '{groups[g]._loaded_from}' and '{groups[c]._loaded_from}'.")

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

def define_special_global_variables(group_all: GroupWrapper) -> None:
    """
    Defines special global variables on the given all group.
    Respects if the corresponding variable is already set.
    """
    if not hasattr(group_all, 'fora_managed'):
        setattr(group_all, 'fora_managed', "This file is managed by fora.")

def load_groups() -> tuple[dict[str, GroupWrapper], list[str]]:
    """
    Loads all groups available in the global inventory, validates their dependencies
    and returns the groups as well as a topological order respecting the dependency declarations.

    Parameters
    ----------
    groups
        The sorted dictionary of groups.

    Returns
    -------
    tuple[dict[str, GroupWrapper], list[str]]
        A dictionary of all loaded group modules index by their name, and a valid topological order
    """
    available_groups = G.inventory.available_groups(G.inventory)
    loaded_groups = {}

    # Store available_groups so it can be accessed while groups are actually loaded.
    # The all group is always made available.
    G.available_groups = available_groups | set(["all"])

    for group_name in available_groups:
        wrapper = GroupWrapper(group_name)
        group_file = G.inventory.group_module_file(G.inventory, group_name)
        if group_file is None:
            wrapper.wrap(DefaultGroup())
        else:
            load_group(wrapper, group_file)
        loaded_groups[group_name] = wrapper

    # Create default "all" group if it wasn't defined explicitly
    if "all" not in available_groups:
        all_wrapper = GroupWrapper("all")
        all_wrapper.wrap(DefaultGroup())
        loaded_groups["all"] = all_wrapper

    # Define special global variables such as `{fora_managed` on the all group.
    define_special_global_variables(loaded_groups["all"])

    # Firstly, deduplicate and unify each group's before and after dependencies,
    # and check for any self-dependencies.
    merge_group_dependencies(loaded_groups)

    # Find a topological order and check the groups for attribute conflicts.
    try:
        topological_order = sort_and_validate_groups(loaded_groups)
    except ValueError as e:
        raise FatalError(str(e))
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

    Raises
    ------
    FatalError
        The connector could not resolved because either none was given or the scheme could not be matched against existing connectors.
    """
    # pylint: disable=protected-access
    if host.connector is None:
        if ':' not in host.url:
            raise FatalError("url doesn't include a schema and no connector was specified explicitly", loc=host._loaded_from)
        schema = host.url.split(':')[0]
        if schema in Connector.registered_connectors:
            host.connector = Connector.registered_connectors[schema]
        else:
            raise FatalError(f"no connector found for schema {schema}", loc=host._loaded_from)

def load_host(name: str, url: str, module_file: Optional[str] = None, requires_module_file: bool = False) -> HostType:
    """
    Loads the specified host with the given name, url and host module file (if any).

    Parameters
    ----------
    name
        The host name of the host to be loaded
    url
        The url for the host
    module_file
        The path to the host module file that will be instanciated.
        Pass None to try loading `hosts/{name}.py` and otherwise fall
        back to instanciating a `DefaultHost` if the name is an url scheme `(*:*)`.
    requires_module_file
        Whether it is an error if the module file does not exist.

    Returns
    -------
    HostType
        The host module
    """
    module_file_exists = module_file is not None and os.path.exists(module_file)
    loaded_from = module_file if module_file is not None and module_file_exists else "<internal>"
    meta = HostType(name=name, _loaded_from=loaded_from, url=url)

    with set_this_host(meta) as ctx:
        fora.host.add_group("all")

        # Instanciate host module file if it exists, else return default host definition
        if module_file is not None and module_file_exists:
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
    Instanciates all hosts in the global inventory and loads any associated host module files.

    Returns
    -------
    dict[str, HostType]
        A mapping from name to host module

    Raises
    ------
    FatalError
        A duplicate host was defined or an invalid host definition was encountered.
    """
    loaded_hosts = {}

    for host in G.inventory.hosts:
        if isinstance(host, str):
            (url, module_file, requires_module_file) = (host, None, False)
        elif isinstance(host, tuple):
            (url, module_file, requires_module_file) = host + (True,)
            module_file = os.path.join(G.inventory.base_dir(G.inventory), module_file)
        else:
            raise FatalError(f"invalid host '{str(host)}'", loc=G.inventory.definition_file())

        # First qualify the url (by default this adds ssh:// to "naked" hostnames)
        url = G.inventory.qualify_url(G.inventory, url)
        # Next extract the "friendly" hostname which we need to find the module file for the host.
        name = G.inventory.extract_hostname(G.inventory, url)

        # Use default module file path if not explicitly given
        if isinstance(host, str):
            module_file = G.inventory.host_module_file(G.inventory, name)

        if name in loaded_hosts:
            raise FatalError(f"duplicate host '{str(host)}'", loc=G.inventory.definition_file())
        loaded_hosts[name] = load_host(name=name, url=url, module_file=module_file, requires_module_file=requires_module_file)

    return loaded_hosts

def load_inventory_object(inventory: Any) -> None:
    """
    Loads the global inventory from the given inventory object.
    in the fora module.

    Parameters
    ----------
    inventory
        The inventory object.
    """
    # The global inventory should now prefer variables from the loaded inventory
    # and only fall back to the defaults if they weren't specified.
    G.inventory.wrap(inventory)

    # Load all groups and hosts from the global inventory.
    G.groups, G.group_order = load_groups()
    G.hosts = load_hosts()

def load_inventory_from_file_or_url(inventory_or_host_url: str) -> None:
    """
    Loads the global inventory from the given filename or single-host url.

    Parameters
    ----------
    inventory_or_host_url
        Either a single host url or an inventory module (`*.py`). If a single host url
        is given without a connection schema (like `ssh://`), ssh will be used.

    Raises
    ------
    FatalError
        The loaded inventory was invalid.
    """
    inv: Any
    if inventory_or_host_url.endswith(".py"):
        # Load inventory from module file
        inv = load_inventory(inventory_or_host_url)
    else:
        # Create an immediate inventory with just the given host.
        inv = ImmediateInventory([inventory_or_host_url])

    load_inventory_object(inv)

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
