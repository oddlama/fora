"""Provides the dynamic module loading utilities."""

import inspect
import os
from types import ModuleType
from typing import Union, cast, Any, Optional

import fora

from fora import globals as G, logger
from fora.types import GroupWrapper, HostWrapper, ScriptWrapper
from fora.utils import FatalError, print_error, load_py_module

script_stack: list[tuple[ScriptWrapper, inspect.FrameInfo]] = []
"""A stack of all currently executed scripts ((name, file), frame)."""

class DefaultGroup:
    """This class will be instanciated for empty groups without associated module files."""

class DefaultHost:
    """
    This class will be instanciated for each host that has not been defined by a corresponding
    host module file, and is used to represent a host with no special configuration.
    """

class ImmediateInventory:
    """A temporary inventory just for a single run, without the ability to load host or group module files."""
    def __init__(self, hosts: list[Union[str, tuple[str, str]]]) -> None:
        self.hosts = list(hosts)

    def base_dir(self) -> str:
        """An immediate inventory has no base directory."""
        _ = (self)
        raise RuntimeError("Immediate inventories have no base directory!")

    def group_module_file(self, name: str) -> Optional[str]: # pylint: disable=useless-return
        """An immediate inventory has no group modules."""
        _ = (self, name)
        return None

    def host_module_file(self, name: str) -> Optional[str]: # pylint: disable=useless-return
        """An immediate inventory has no host modules."""
        _ = (self, name)
        return None

    def available_groups(self) -> set[str]:
        """An immediate inventory has no groups."""
        _ = (self)
        return set()

def load_group(name: str, module_file: Optional[str]) -> GroupWrapper:
    """
    Loads and validates a group definition from the given file.

    Parameters
    ----------
    name
        The name of the group to load.
    module_file
        The path to the file containing to the group definition, or None to instanciate a DefaultGroup (similar to an empty module).

    Returns
    -------
    GroupWrapper
        The loaded group.
    """
    wrapper = GroupWrapper(name)
    if module_file is None:
        wrapper.wrap(DefaultGroup())
        return wrapper

    def _pre_exec(module: ModuleType) -> None:
        fora.group = wrapper
        wrapper.wrap(module, copy_members=True, copy_functions=True)

        if wrapper.name == "all":
            # Add predefined global variables before the "all" group module is instanciated
            add_predefined_global_variables(wrapper)
        else:
            # Normal groups always have a dependency on the global "all" group.
            wrapper.after("all")

    # Instanciate module
    load_py_module(module_file, pre_exec=_pre_exec)
    fora.group = cast(GroupWrapper, None)
    return wrapper

def add_predefined_global_variables(group_all: GroupWrapper) -> None:
    """
    Predefines global variables on the given all group. This includes
    variables set by the inventory, as they can be overridden by the "all" group.
    """
    setattr(group_all, 'fora_managed', "This file is managed by fora.")
    for key, val in fora.inventory.global_variables().items():
        setattr(group_all, key, val)

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
    available_groups = fora.inventory.available_groups()
    loaded_groups = {}

    # Store available_groups so it can be accessed while groups are actually loaded.
    # The all group is always made available.
    G.available_groups = available_groups | set(["all"])

    # Load all groups that were defined by the inventory
    for group_name in available_groups:
        loaded_groups[group_name] = load_group(group_name, fora.inventory.group_module_file(group_name))

    # Create default "all" group if it wasn't defined explicitly
    if "all" not in available_groups:
        all_wrapper = GroupWrapper("all")
        all_wrapper.wrap(DefaultGroup())
        add_predefined_global_variables(all_wrapper)
        loaded_groups["all"] = all_wrapper

    # Firstly, deduplicate and unify each group's before and after dependencies,
    # and check for any self-dependencies.
    merge_group_dependencies(loaded_groups)

    # Find a topological order and check the groups for attribute conflicts.
    try:
        topological_order = sort_and_validate_groups(loaded_groups)
    except ValueError as e:
        raise FatalError(str(e)) from E
    return (loaded_groups, topological_order)

def load_host(name: str, url: str, module_file: Optional[str] = None, requires_module_file: bool = False) -> HostWrapper:
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
    HostWrapper
        The host module
    """
    module_file_exists = module_file is not None and os.path.exists(module_file)
    wrapper = HostWrapper(name, url)
    # All hosts implicitly belong to the "all" group
    wrapper.groups.add("all")

    # Instanciate host module file if it exists, else return default host definition
    if module_file is None or not module_file_exists:
        if requires_module_file:
            raise ValueError(f"Required module file '{module_file}' for host '{name}' does not exist")
        wrapper.wrap(DefaultHost())
    else:
        def _pre_exec(module: ModuleType) -> None:
            fora.host = wrapper
            wrapper.wrap(module, copy_members=True, copy_functions=True)

        load_py_module(module_file, pre_exec=_pre_exec)
        fora.host = cast(HostWrapper, None)

    return wrapper

def load_hosts() -> dict[str, HostWrapper]:
    """
    Instanciates all hosts in the global inventory and loads any associated host module files.

    Returns
    -------
    dict[str, HostWrapper]
        A mapping from name to host module

    Raises
    ------
    FatalError
        A duplicate host was defined or an invalid host definition was encountered.
    """
    loaded_hosts = {}

    for host in fora.inventory.hosts:
        if isinstance(host, str):
            (url, module_file, requires_module_file) = (host, None, False)
        elif isinstance(host, tuple):
            (url, module_file, requires_module_file) = host + (True,)
            module_file = os.path.join(fora.inventory.base_dir(), module_file)
        else:
            raise FatalError(f"Invalid host '{str(host)}'", loc=fora.inventory.definition_file())

        # First qualify the url (by default this adds ssh:// to "naked" hostnames)
        url = fora.inventory.qualify_url(url)
        # Next extract the "friendly" hostname which we need to find the module file for the host.
        name = fora.inventory.extract_hostname(url)

        # Use default module file path if not explicitly given
        if isinstance(host, str):
            module_file = fora.inventory.host_module_file(name)

        if name in loaded_hosts:
            raise FatalError(f"Duplicate host '{str(host)}'", loc=fora.inventory.definition_file())
        loaded_hosts[name] = load_host(name=name, url=url, module_file=module_file, requires_module_file=requires_module_file)

    return loaded_hosts

def load_inventory(inventory_file_or_host_url: str) -> None:
    """
    Loads the global inventory from the given filename or single-host url
    and validates the definintions.

    Parameters
    ----------
    inventory_file_or_host_url
        Either a single host url or an inventory module file (`*.py`). If a single host url
        is given without a connection schema (like `ssh://`), ssh will be used.

    Raises
    ------
    FatalError
        The loaded inventory was invalid.
    """
    G.inventory_loaded = False
    wrapper = InventoryWrapper()
    fora.inventory = wrapper

    if inventory_file_or_host_url.endswith(".py"):
        # Load inventory from module file
        def _pre_exec(module: ModuleType) -> None:
            wrapper.wrap(module)

        inv = load_py_module(inventory_file_or_host_url, pre_exec=_pre_exec)

        # Check that the hosts definition is valid.
        if not hasattr(inv, "hosts"):
            raise FatalError("Inventory must define a list of hosts!", loc=wrapper.definition_file())
        hosts = getattr(inv, "hosts")
        if not isinstance(hosts, list):
            raise FatalError(f"`hosts` definition must be of type list, not {type(hosts)}!", loc=wrapper.definition_file())
    else:
        # Create an immediate inventory with just the given host.
        wrapper.wrap(ImmediateInventory([inventory_file_or_host_url]))

    try:
        wrapper.preprocess_inventory()
    except ValueError as e:
        raise FatalError(str(e), loc=wrapper.definition_file()) from None

    # Load all groups and hosts from the global inventory.
    wrapper.load_groups()
    G.hosts = load_hosts()
    G.inventory_loaded = True

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

        wrapper = ScriptWrapper(name)
        script_stack.append((wrapper, frame))
        try:
            previous_script = fora.script
            previous_working_directory = os.getcwd()
            canonical_script = os.path.realpath(script)

            # Change into script's containing directory, so a script
            # can reliably use relative paths while it is executed.
            new_working_directory = os.path.dirname(canonical_script)
            os.chdir(new_working_directory)

            try:
                fora.script = wrapper
                # New script instance should start with a fresh set of default values.
                # Therefore, we use defaults() here to apply the connection's base settings.
                with wrapper.defaults():
                    def _pre_exec(module: ModuleType) -> None:
                        wrapper.wrap(module, copy_members=True, copy_functions=True)
                        setattr(module, '_params', params or {})
                    load_py_module(canonical_script, pre_exec=_pre_exec)
            finally:
                os.chdir(previous_working_directory)
                fora.script = previous_script
        except Exception as e:
            # Save the current script_stack in any exception thrown from this context
            # for later use in any exception handler.
            if not hasattr(e, 'script_stack'):
                setattr(e, 'script_stack', script_stack.copy())
            raise
        finally:
            script_stack.pop()
