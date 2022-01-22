"""
Provides the top-level logic of fora such as
the CLI interface and main script dispatching.
"""

import argparse
import inspect
import os
import sys
from types import ModuleType
from typing import Any, Callable, NoReturn, Optional, cast

import fora
from fora.connection import open_connection
from fora.example_deploys import init_deploy_structure
from fora.loader import load_inventory, run_script
from fora.logger import col
from fora.types import GroupWrapper, HostWrapper, ModuleWrapper, VariableActionSnapshot
from fora.utils import FatalError, die_error, install_exception_hook, print_fullwith, print_table
from fora.version import version

def main_run(args: argparse.Namespace) -> None:
    """
    Main method used to run a script on an inventory.

    Parameters
    ----------
    args
        The parsed arguments
    """
    try:
        load_inventory(args.inventory)
    except FatalError as e:
        die_error(str(e), loc=e.loc)

    # Deduplicate host selection and check if every host is valid
    selected_hosts = []
    for host in (args.hosts.split(",") if args.hosts is not None else fora.inventory.loaded_hosts):
        # Skip duplicate entries
        if host in selected_hosts:
            continue
        # Ensure host existence
        if host not in fora.inventory.loaded_hosts:
            die_error(f"Unknown host '{host}'")
        selected_hosts.append(host)

    # TODO: multiprocessing?
    # - displaying must then be handled by ncurses which makes things a lot more complex.
    # - would open the door to a more interactive experience, e.g. allow to select past operations
    #   and view information about them, scroll through diffs, ...
    # - we need to save some kind of log file as the output won't persist in the terminal
    # - fatal errors must be delayed until all executions are fininshed.

    # Instanciate (run) the given script for each selected host
    for host in fora.inventory.loaded_hosts.values():
        with open_connection(host):
            fora.host = host
            run_script(args.script, inspect.getouterframes(inspect.currentframe())[0], name="cmdline")
            fora.host = cast(HostWrapper, None)

        if host.name != selected_hosts[-1]:
            # Separate hosts by a newline for better visibility
            print()

def show_inventory(inventory: str) -> None:
    """
    Display a summary of the given inventory.

    Parameters
    ----------
    inventory
        The inventory argument
    """
    # pylint: disable=protected-access,too-many-branches,too-many-statements
    try:
        load_inventory(inventory)
    except FatalError as e:
        die_error(str(e), loc=e.loc)

    col_red      = col("\033[31m")
    col_red_b    = col("\033[1;31m")
    col_green    = col("\033[32m")
    col_green_b  = col("\033[1;32m")
    col_yellow   = col("\033[33m")
    col_blue     = col("\033[34m")
    col_darker   = col("\033[90m")
    col_darker_b = col("\033[1;90m")
    col_reset    = col("\033[m")

    try:
        base_dir = fora.inventory.base_dir()
    except RuntimeError:
        base_dir = "."

    def relpath(path: Optional[str]) -> Optional[str]:
        return None if path is None else os.path.relpath(path, start=base_dir)

    def value_repr(x: Any) -> list[str]:
        color = col_reset
        if x is None:
            color = col_red
        elif isinstance(x, bool):
            color = col_green if x else col_red
        elif isinstance(x, (list, tuple, range, dict, set)):
            color = col_blue
        elif isinstance(x, (str, bytes)):
            color = col_green
        elif isinstance(x, (int, float)):
            color = col_yellow
        else:
            color = col_darker

        return [color, repr(value), col_reset]

    def precedence(wrapper: ModuleWrapper) -> int:
        """Calculates a numeric variable precedence in accordance with the hierachical lookup rules."""
        if isinstance(wrapper, GroupWrapper):
            return fora.inventory._topological_order.index(wrapper.name)
        if isinstance(wrapper, HostWrapper):
            return len(fora.inventory._topological_order)
        return -1

    print_fullwith(["──────── ", col_red_b, "inventory", col_reset, " ", col_darker_b, inventory, col_reset, " "], [col_darker, f" {relpath(fora.inventory.definition_file())}", col_reset])

    pretty_group_names = { name: f"{col_darker}- ({index}){col_reset} {col_yellow}{name}{col_reset}" for index,name in enumerate(fora.inventory._topological_order) }
    print(f"{col_blue}groups{col_reset} {col_darker}(precedence, low to high){col_reset}")
    for i in pretty_group_names.values():
        print(f"  {i}")

    pretty_host_names = { name: f"{col_darker}-{col_reset} {col_green}{name}{col_reset} {col_darker}({host.url}, {relpath(host.definition_file())}){col_reset}" for name,host in fora.inventory.loaded_hosts.items() }
    print(f"{col_blue}hosts{col_reset} {col_darker}(url, module){col_reset}")
    for i in pretty_host_names.values():
        print(f"  {i}")

    if len(fora.inventory.global_variables()) > 0:
        print(f"{col_blue}variables{col_reset}")
        for attr, value in fora.inventory.global_variables().items():
            print(f"{col_green}{attr}{col_reset}\t(type {type(value)}) = {value}")

    for name, host in fora.inventory.loaded_hosts.items():
        print()
        print_fullwith(["──────── ", col_red_b, "host", col_reset, " ", col_green_b, name, col_reset, " "], [col_darker, f" {relpath(host.definition_file())}", col_reset])
        entries = []
        for attr, value in host.vars_hierarchical().items():
            if attr.startswith("_") or isinstance(value, ModuleType):
                continue
            is_declared_by_wrapper = attr in HostWrapper.__dict__ or attr in HostWrapper.__annotations__
            last_actor = host._variable_action_history.get(attr, [VariableActionSnapshot("definition", host, value)])[-1].actor
            entries.append((attr, value, is_declared_by_wrapper, last_actor))

        table = []
        for attr, value, is_declared_by_wrapper, last_actor in sorted(entries, key=lambda tup: (not tup[2], precedence(tup[3]), tup[0])):
            definition_str: list[str] = []
            for action in reversed(host._variable_action_history.get(attr, [VariableActionSnapshot("definition", host, value)])):
                if isinstance(action.actor, GroupWrapper):
                    definition_str = [col_darker, f"({precedence(action.actor)}) ", col_reset, col_yellow, action.actor.name, col_reset, col_darker, ", ", col_reset] + definition_str
                elif isinstance(action.actor, HostWrapper):
                    definition_str = [col_darker, f"({precedence(action.actor)}) ", col_reset, col_green, action.actor.name, col_reset, col_darker, ", ", col_reset] + definition_str
                if action.action == "definition":
                    break

            # Strip last ", "
            definition_str = definition_str[:-3]

            col_var = col_darker
            if is_declared_by_wrapper:
                if host.is_overridden(attr):
                    col_var = col_darker_b
                else:
                    col_var = col_darker
            elif isinstance(last_actor, GroupWrapper):
                col_var = col_yellow
            elif isinstance(last_actor, HostWrapper):
                col_var = col_green
            else:
                col_var = col_reset

            table.append([[col_var, attr, col_reset], [col_darker, type(value).__name__, col_reset], definition_str, value_repr(value)])
        print_table([[col_blue, "variable", col_reset],
                     [col_blue, "type", col_reset],
                     [col_darker, "(prec) ", col_reset, col_blue, "defined by", col_reset],
                     [col_blue, "value", col_reset]],
                     table, min_col_width=[24, 0, 12, 0])

    sys.exit(0)

class ArgumentParserError(Exception):
    """Error class for argument parsing errors."""

class ThrowingArgumentParser(argparse.ArgumentParser):
    """An argument parser that throws when invalid argument types are passed."""

    def error(self, message: str) -> NoReturn:
        """Raises an exception on error."""
        raise ArgumentParserError(message)

class ActionImmediateFunction(argparse.Action):
    """An action that calls a function immediately when the argument is encountered."""
    def __init__(self, option_strings: Any, func: Callable[[Any], Any], *args: Any, **kwargs: Any):
        self.func = func
        super().__init__(option_strings, *args, **kwargs)

    def __call__(self, parser: argparse.ArgumentParser, namespace: argparse.Namespace, values: Any, option_string: Any = None) -> None:
        _ = (parser, namespace, values, option_string)
        self.func(values)

def main(argv: Optional[list[str]] = None) -> None:
    """
    The main program entry point. This will parse arguments, load inventory and task
    definitions and run the given user script. Defaults to sys.argv[1:] if argv is None.
    """
    if argv is None:
        argv = sys.argv[1:]
    parser = ThrowingArgumentParser(description="Runs a fora script.")

    # General options
    parser.add_argument('-V', '--version', action='version',
            version=f"%(prog)s version {version}")

    # Run script options
    parser.add_argument('--init', action=ActionImmediateFunction, func=init_deploy_structure, choices=["minimal", "flat", "dotfiles", "modular", "staging_prod"],
            help="Initialize the current directory with a default deploy structure and exit. The various choices are explained in-depth in the documentation. As a rule of thumb, 'minimal' is the most basic starting point, 'flat' is well-suited for small and simple deploys, 'dotfiles' is explicitly intended for dotfile deploys, 'modular' is the most versatile layout intended to be used with modular sub-tasks, and 'staging_prod' is the modular layout with two separate inventories.")
    parser.add_argument('--inspect-inventory', action=ActionImmediateFunction, func=show_inventory,
            help="Display all available information about a specific inventory. This includes a summary as well as the specific variables available on each group or host.")
    parser.add_argument('-H', '--hosts', dest='hosts', default=None, type=str,
            help="Specifies a comma separated list of hosts to run on. By default all hosts are selected. Duplicates will be ignored.")
    parser.add_argument('--dry', '--dry-run', '--pretend', dest='dry', action='store_true',
            help="Print what would be done instead of performing any actions. Probing commands will still be executed to determine the current state of the systems.")
    parser.add_argument('-v', '--verbose', dest='verbose', action='count', default=0,
            help="Increase output verbosity. Can be given multiple times.")
    parser.add_argument('--no-changes', dest='changes', action='store_false',
            help="Don't display changes for each operation in a short diff-like format.")
    parser.add_argument('--diff', dest='diff', action='store_true',
            help="Display an actual diff when an operation changes a file. Use with care, as this might print secrets!")
    parser.add_argument('--debug', dest='debug', action='store_true',
            help="Enable debugging output. Forces verbosity to max value.")
    parser.add_argument('--no-color', dest='no_color', action='store_true',
            help="Disables any color output. Color can also be disabled by setting the NO_COLOR environment variable.")
    parser.add_argument('inventory', type=str,
            help="The inventory to run on. Either a single host url or an inventory module (`*.py`). If a single host url is given without a connection schema (like `ssh://`), ssh will be used. Single hosts also do not load any groups or host modules.")
    parser.add_argument('script', type=str,
            help="The user script containing the logic of what should be executed on the inventory.")
    parser.set_defaults(func=main_run)

    try:
        args: argparse.Namespace = parser.parse_args(argv)
    except ArgumentParserError as e:
        die_error(str(e))

    # Force max verbosity with --debug
    if args.debug:
        args.verbose = 99

    # Disable color when NO_COLOR is set
    if os.getenv("NO_COLOR") is not None:
        args.no_color = True

    # Install exception hook to modify traceback, if debug isn't set.
    # Exceptions raised from a dynamically loaded module will then
    # be displayed a lot cleaner.
    if not args.debug:
        install_exception_hook()

    if 'func' not in args:
        # Fallback to --help.
        parser.print_help()
    else:
        fora.args = args
        args.func(args)
