"""
Provides the top-level logic of fora such as
the CLI interface and main script dispatching.
"""

import argparse
import inspect
import os
import sys
from typing import Any, Callable, NoReturn, Optional, cast

import fora
from fora import globals as G
from fora.connection import open_connection
from fora.example_deploys import init_deploy_structure
from fora.loader import load_inventory, run_script
from fora.types import HostWrapper
from fora.utils import FatalError, die_error, install_exception_hook
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
    host_names = []
    for h in set(args.hosts.split(",") if args.hosts is not None else G.hosts.keys()):
        if h not in G.hosts:
            die_error(f"Unknown host '{h}'")
        host_names.append(h)
    host_names = sorted(host_names)

    # TODO: multiprocessing?
    # - displaying must then be handled by ncurses which makes things a lot more complex.
    # - would open the door to a more interactive experience, e.g. allow to select past operations
    #   and view information about them, scroll through diffs, ...
    # - we need to save some kind of log file as the output won't persist in the terminal
    # - fatal errors must be delayed until all executions are fininshed.

    # Instanciate (run) the given script for each selected host
    for h in host_names:
        host = G.hosts[h]

        with open_connection(host):
            fora.host = host
            run_script(args.script, inspect.getouterframes(inspect.currentframe())[0], name="cmdline")
            fora.host = cast(HostWrapper, None)

        if h != host_names[-1]:
            # Separate hosts by a newline for better visibility
            print()

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
        G.args = args
        args.func(args)
