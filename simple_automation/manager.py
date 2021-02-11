from simple_automation.version import __version__
from simple_automation.group import Group
from simple_automation.host import Host
from simple_automation.task import Task
from simple_automation.checks import check_valid_key
from simple_automation.context import Context
from simple_automation.exceptions import SimpleAutomationError, MessageError, LogicError
from simple_automation.vars import Vars

from jinja2 import Environment, FileSystemLoader, StrictUndefined

import os
import argparse

class ArgumentParserError(Exception):
    pass

class ThrowingArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        raise ArgumentParserError(message)

class Manager(Vars):
    """
    A class that manages a set of global variables, hosts, groups, and
    tasks. It provides the CLI interface and represents the main entry
    point for a simple automation script.
    """
    def __init__(self, inventory_class, main_directory=None):
        """
        Create a new manager, which will instanciate the given inventory class.
        All relative paths (mainly files used in basic.template() or basic.copy()) will
        be interpreted relative from the location of the initially executed script. If
        you want to change this behavior, you can either set main_directory to a relative
        path, which will then be appended to that location, or to an absolute path.
        """
        super().__init__()

        self.groups = {}
        self.hosts = {}
        self.tasks = {}
        self.vaults = {}

        self.pretend = True
        self.verbose = 0
        self.debug = False

        # Find the directory of the initially called script
        import inspect
        first_frame = inspect.getouterframes(inspect.currentframe())[-1]
        main_script_directory = os.path.abspath(os.path.dirname(first_frame.filename))

        # Find the main directory
        if main_directory is None:
            self.main_directory = main_script_directory
        else:
            self.main_directory = os.path.realpath(os.path.join(main_script_directory, main_directory))

        self.jinja2_env = Environment(
            loader=FileSystemLoader(self.main_directory, followlinks=True),
            autoescape=False,
            undefined = StrictUndefined)
        self.set("simple_automation_managed", "This file is managed by simple automation.")

        # Create inventory
        self.inventory = inventory_class(self)

    def add_group(self, identifier):
        """
        Registers a new group.
        """
        check_valid_key(identifier, msg="Invalid group identifier")
        group = Group(self, identifier)
        if identifier in self.groups:
            raise LogicError(f"Cannot register group: Duplicate identifier {identifier}")
        self.groups[identifier] = group
        return group

    def add_host(self, identifier, ssh_host):
        """
        Registers a new host.
        """
        check_valid_key(identifier, msg="Invalid host identifier")
        host = Host(self, identifier, ssh_host)
        if identifier in self.hosts:
            raise LogicError(f"Cannot register host: Duplicate identifier {identifier}")
        self.hosts[identifier] = host
        return host

    def add_task(self, task_class):
        """
        Registers a given task class. This allows the task to register
        variable defaults. You can either save the returned instance yourself
        and call task.exec() when you want to run it, or you can use context.run_task(task_class)
        to run a registered task automatically.
        """
        identifier = task_class.identifier
        check_valid_key(identifier, msg="Invalid task identifier")
        if identifier in self.tasks:
            raise LogicError(f"Cannot register task: Duplicate identifier {identifier}")

        # We want the manager to warn when a variable is redefined
        # on task instanciation.
        self.warn_on_redefinition = True
        task = task_class(self)
        self.warn_on_redefinition = False

        self.tasks[identifier] = task
        return task

    def add_vault(self, vault_class, file, **kwargs):
        """
        Registers a vault of the given class, with its storage at file.
        Additional parameters are forwarded to the vault constructor.
        """
        canonical_path = os.path.realpath(os.path.join(self.main_directory, file))
        if canonical_path in self.vaults:
            raise LogicError(f"Duplicate vault: Another vault with file='{canonical_path}' has already been defined!")
        vault = vault_class(manager=self, file=canonical_path, **kwargs)
        self.vaults[canonical_path] = vault
        return vault

    def main(self):
        """
        The main program entry point. This will parse arguments and call the
        user-supplied function on the defined inventory, when the script should be executed.
        """

        # Stop accepting new registrations, which would not be handeled correctly
        # when done dynamically. (e.g. Variable default registrations would be skipped for tasks)
        self.accept_registrations = False

        parser = ThrowingArgumentParser(description="Runs this simple automation script.")

        # General options
        parser.add_argument('-e', '--edit-vault', dest='edit_vault', default=None, type=str,
                help="Edit the given vault instead of running the main script.")
        parser.add_argument('-H', '--hosts', dest='hosts', default=None, type=list,
                help="Specifies a comma separated list of hosts to run on. By default all hosts are selected. Duplicates will be ignored.")
        parser.add_argument('-p', '--pretend', dest='pretend', action='store_true',
                help="Print what would be done instead of performing the actions.")
        parser.add_argument('-v', '--verbose', dest='verbose', action='count', default=0,
                help="Increase output verbosity. Can be given multiple times. Typically, no information will be filtered with -vvv.")
        parser.add_argument('--debug', dest='debug', action='store_true',
                help="Enable debugging output.")
        parser.add_argument('--version', action='version',
                version=f"%(prog)s built with simple_automation version {__version__}")

        try:
            args = parser.parse_args()
        except ArgumentParserError as e:
            print("error: " + str(e))
            exit(1)

        self.pretend = args.pretend
        self.verbose = args.verbose
        self.debug = args.debug

        try:
            self.edit_vault = args.edit_vault
            if self.edit_vault is not None:
                # Let the inventory register vaults
                self.inventory.register_vaults()

                # Retrieve vault
                canonical_path = os.path.realpath(os.path.join(self.main_directory, self.edit_vault))
                if canonical_path not in self.vaults:
                    raise MessageError(f"No registered vault matches the given file '{canonical_path}'!")
                vault = self.vaults[canonical_path]

                # Load vault content, then launch editor
                vault.decrypt()
                vault.edit()
            else:
                # Load and decrypt all vaults
                self.inventory.register_vaults()
                for v in self.vaults.values():
                    v.decrypt()

                # Let the inventory register everything else
                self.inventory.register_tasks()
                self.inventory.register_globals()
                self.inventory.register_inventory()

                # Check if host selection is valid
                hosts = []
                for h in args.hosts if args.hosts is not None else self.hosts.keys():
                    if h not in self.hosts:
                        raise MessageError(f"Unkown host {h}")
                    hosts.append(self.hosts[h])
                hosts = sorted(set(hosts))

                # Run for each selected host
                for host in hosts:
                    with Context(self, host) as c:
                        self.inventory.run(c)
        except MessageError as e:
            print(f"[1;31merror:[m {str(e)}")
        except SimpleAutomationError as e:
            print(f"[1;31merror:[m {str(e)}")
            raise e
