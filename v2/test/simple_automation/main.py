"""
Provides the top-level logic of simple_automation such as
the CLI interface and coordination of submodule loading.
"""

import argparse

import simple_automation
from simple_automation.loader import load_site
from simple_automation.utils import die_error
from simple_automation.version import __version__

from jinja2 import Environment, FileSystemLoader, StrictUndefined

# TODO self.set("simple_automation_managed", "This file is managed by simple automation.")

def main_edit_vault(args):
    pass
    # Load vault content, then launch editor
    #vault.decrypt()
    #vault.edit()

def init_runtime():
    simple_automation.jinja2_env = Environment(
            loader=FileSystemLoader('.', followlinks=True),
            autoescape=False,
            undefined=StrictUndefined)

def main_run(args):
    init_runtime()
    load_site(args.inventory)

    ## Check if host selection is valid
    #hosts = []
    #for h in args.hosts.split(',') if args.hosts is not None else self.hosts.keys():
    #    if h not in self.hosts:
    #        raise MessageError(f"Unkown host '{h}'")
    #    hosts.append(self.hosts[h])
    #hosts = sorted(set(hosts))

    ## Run for each selected host
    #for host in hosts:
    #    with Context(self, host) as c:
    #        for script in args.scripts.split(','):
    #            fn = getattr(self.inventory, script)
    #            fn(c)

class ArgumentParserError(Exception):
    """
    Error class for argument parsing errors.
    """

class ThrowingArgumentParser(argparse.ArgumentParser):
    """
    An argument parser that throws when invalid argument types are passed.
    """

    def error(self, message):
        """
        Raises an exception on error.
        """
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
    parser.add_argument('-p', '--pretend', '--dry', '--dry-run', dest='pretend', action='store_true',
            help="Print what would be done instead of performing any actions. Probing commands will still be executed to determine the current state of a system.")
    parser.add_argument('-v', '--verbose', dest='verbose', action='count', default=0,
            help="Increase output verbosity. Can be given multiple times. Typically, everything will be printed with -vvv.")
    parser.add_argument('--debug', dest='debug', action='store_true',
            help="Enable debugging output.")
    parser.add_argument('script', type=str, nargs=1,
            help="The user script containing the logic of what should be executed on the inventory.")
    parser.add_argument('inventory', type=str, nargs='+',
            help="The inventories on which the script should be run on. A inventory is either a full inventory module file (determined by the presenence of a .py extension, e.g. inventory.py), or a single-host defined in any syntax that is accepted by ssh (e.g. root@localhost or ssh://[user]@host)")
    parser.set_defaults(func=main_run)

    try:
        args = parser.parse_args()
    except ArgumentParserError as e:
        die_error(str(e))

    if 'func' not in args:
        # Fallback to --help.
        parser.print_help()
    else:
        args.func(args)
