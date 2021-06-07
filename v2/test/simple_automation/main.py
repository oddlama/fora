"""
Provides the top-level logic of simple_automation such as
the CLI interface and submodule loading.
"""

import argparse

import simple_automation
from simple_automation.utils import die_error, load_py_module
from simple_automation.version import __version__

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

# TODO self.set("simple_automation_managed", "This file is managed by simple automation.")

def main_edit_vault(args):
    pass
    # Load vault content, then launch editor
    #vault.decrypt()
    #vault.edit()

class HostDefinition:
    def __init__(self, name, definition_file):
        self.name = name
        self.definition_file = definition_file

def load_host(host):
    print(f"loading host {host.name} from {host.definition_file}")
    simple_automation.host = host
    return load_py_module(host.definition_file)

def main_run(args):
    from jinja2 import Environment, FileSystemLoader, StrictUndefined

    simple_automation.jinja2_env = Environment(
            loader=FileSystemLoader('.', followlinks=True),
            autoescape=False,
            undefined=StrictUndefined)

    simple_automation.inventory = load_py_module('inventory.py')
    if not hasattr(simple_automation.inventory, 'hosts'):
        die_error("inventory.py: Inventory must define a list of hosts!")
    if not isinstance(simple_automation.inventory.hosts, list):
        die_error("inventory.py: hosts variable must be a list!")

    loaded_hosts = []
    for host in simple_automation.inventory.hosts:
        if isinstance(host, str):
            loaded_hosts.append(load_host(HostDefinition(host, f"hosts/{host}.py")))
        elif isinstance(host, tuple):
            (name, definition_py) = host
            loaded_hosts.append(load_host(HostDefinition(name, definition_py)))
        elif isinstance(host, HostDefinition):
            loaded_hosts.append(load_host(host))
        else:
            die_error(f"inventory.py: invalid host '{str(host)}'")
    simple_automation.inventory.hosts = loaded_hosts

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

def main():
    """
    The main program entry point. This will parse arguments, load inventory and task
    definitions and run the given user script.
    """

    parser = ThrowingArgumentParser(description="Runs this simple automation script.")
    subparsers = parser.add_subparsers(title="commands",
            description="Use '%(prog)s command --help' to view the help for a given command.",
            metavar='command')

    # General options
    parser.add_argument('--version', action='version',
            version=f"%(prog)s version {__version__}")

    # Edit-vault options
    parser_edit_vault = subparsers.add_parser('edit', help='Edit or create the given vault file with $EDITOR.')
    parser_edit_vault.add_argument('vault_file', type=str, nargs=1,
            help="The vault file to edit or create. Launches $EDITOR.")
    parser_edit_vault.set_defaults(func=main_edit_vault)

    # Run options
    parser_run = subparsers.add_parser('run', help='Run a given user script on the inventory.')
    parser_run.add_argument('-H', '--hosts', dest='hosts', default=None, type=str,
            help="Specifies a comma separated list of hosts to run on. By default all hosts are selected. Duplicates will be ignored.")
    parser_run.add_argument('-p', '--pretend', '--dry', '--dry-run', dest='pretend', action='store_true',
            help="Print what would be done instead of performing any actions. Probing commands will still be executed to determine the current state of a system.")
    parser_run.add_argument('-v', '--verbose', dest='verbose', action='count', default=0,
            help="Increase output verbosity. Can be given multiple times. Typically, everything will be printed with -vvv.")
    parser_run.add_argument('--debug', dest='debug', action='store_true',
            help="Enable debugging output.")
    parser_run.add_argument('script', type=str, nargs=1,
            help="The user script containing the logic of what should be executed on the inventory.")
    parser_run.set_defaults(func=main_run)

    try:
        args = parser.parse_args()
    except ArgumentParserError as e:
        die_error(str(e))

    if 'func' not in args:
        # Fallback to --help.
        parser.print_help()
    else:
        args.func(args)