"""Provides the dynamic module loading utilities."""

import inspect
import os
from types import ModuleType
from typing import Union, Any, Optional

import fora

from fora import logger
from fora.inventory_wrapper import InventoryWrapper
from fora.types import ScriptWrapper
from fora.utils import FatalError, load_py_module

script_stack: list[tuple[ScriptWrapper, inspect.FrameInfo]] = []
"""A stack of all currently executed scripts ((name, file), frame)."""

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
        wrapper.load()
    except ValueError as e:
        raise FatalError(str(e), loc=wrapper.definition_file()) from e

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
