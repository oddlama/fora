"""
Provides the top-level logic of simple_automation such as
the CLI interface and main script dispatching.
"""

import argparse
import inspect
import os
from jinja2 import Environment, FileSystemLoader, StrictUndefined

from simple_automation import globals, logger
from simple_automation.connection import open_connection
from simple_automation.loader import load_site, run_script
from simple_automation.utils import die_error, install_exception_hook, set_current_host
from simple_automation.version import __version__

def init_runtime():
    """Initializes runtime variables needed to run scripts."""
    globals.jinja2_env = Environment(
            loader=FileSystemLoader('.', followlinks=True),
            autoescape=False,
            undefined=StrictUndefined)

def main_run(args: argparse.Namespace):
    """
    Main method used to run a script on an inventory.

    Parameters
    ----------
    args
        The parsed arguments
    """
    init_runtime()
    load_site(args.inventory)

    # Deduplicate host selection and check if every host is valid
    host_names = []
    for h in set(args.hosts.split(',') if args.hosts is not None else globals.hosts.keys()):
        if h not in globals.hosts:
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
        host = globals.hosts[h]

        logger.print_indented(f"{logger.col('[1;34m')}host{logger.col('[m')} {host.name}")
        with open_connection(host):
            with set_current_host(host):
                run_script(args.script, inspect.getouterframes(inspect.currentframe())[0], name="Commandline argument")

        # Separate hosts by a newline for better visibility
        print()

class ArgumentParserError(Exception):
    """Error class for argument parsing errors."""

class ThrowingArgumentParser(argparse.ArgumentParser):
    """An argument parser that throws when invalid argument types are passed."""

    def error(self, message):
        """Raises an exception on error."""
        raise ArgumentParserError(message)

def main():
    """
    The main program entry point. This will parse arguments, load inventory and task
    definitions and run the given user script.
    """
    parser = ThrowingArgumentParser(description="Runs a simple automation script.")

    # General options
    parser.add_argument('--version', action='version',
            version=f"%(prog)s version {__version__}")

    # Run script options
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
    parser.add_argument('inventory', type=str, nargs='+',
            help="The inventories on which the script should be run on. A inventory is either a full inventory module file (determined by the presenence of a .py extension, e.g. inventory.py), or a single-host defined in any syntax that is accepted by ssh (e.g. root@localhost or ssh://[user]@host)")
    parser.add_argument('script', type=str,
            help="The user script containing the logic of what should be executed on the inventory.")
    parser.set_defaults(func=main_run)

    try:
        args: argparse.Namespace = parser.parse_args()
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
        globals.args = args
        args.func(args)
