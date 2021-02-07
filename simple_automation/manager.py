from simple_automation.version import __version__
from simple_automation.group import Group
from simple_automation.host import Host
from simple_automation.task import Task
from simple_automation.checks import check_valid_key
from simple_automation.context import Context
from simple_automation.exceptions import SimpleAutomationError, TransactionError, LogicError
from simple_automation.vars import Vars

from jinja2 import Environment, FileSystemLoader

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
    def __init__(self, main_directory=None):
        """
        Create a new manager.
        All relative paths (mainly files used in basic.template() or basic.copy()) will
        be interpreted relative from the location of the initially executed script. If
        you want to change this behavior, you can either set main_directory to a relative
        path, which will then be appended to that location, or to an absolute path.
        """
        super().__init__()

        self.groups = {}
        self.hosts = {}
        self.tasks = {}

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
            autoescape=False)
        self.set("simple_automation_managed", "This file is managed by simple automation.")

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
            raise Exception(f"Cannot register task: Duplicate identifier {identifier}")
        task = task_class(self)
        self.tasks[identifier] = task
        return task

    def main(self, run):
        """
        Run the user-supplied function on the defined inventory.
        """

        # Stop accepting new registrations, which would not be handeled correctly
        # when done dynamically. (e.g. Variable default registrations would be skipped for tasks)
        self.accept_registrations = False

        parser = ThrowingArgumentParser(description="Runs this simple automation script.")

        # General options
        parser.add_argument('-H', '--hosts', dest='hosts', default=None, type=list,
                help="Specifies a subset of hosts to run on. By default all hosts are selected.")
        parser.add_argument('-p', '--pretend', dest='pretend', action='store_true',
                help="Print what would be done instead of performing the actions.")
        parser.add_argument('-v', '--verbose', dest='verbose', action='count', default=0,
                help="Increase output verbosity. Can be given multiple times. Typically, no information will be filtered with -vvv.")
        parser.add_argument('--debug', dest='debug', action='store_true',
                help="Enable debugging output.")
        parser.add_argument('--version', action='version',
                version='%(prog)s built with simple_automation version {version}'.format(version=__version__))

        try:
            args = parser.parse_args()
        except ArgumentParserError as e:
            print("error: " + str(e))
            exit(1)

        self.pretend = args.pretend
        self.verbose = args.verbose
        self.debug = args.debug

        # TODO ask for vault key, vaultdecrypt = ask = [openssl - ...], gpg = []
        try:
            with Context(self, self.hosts["my_laptop"]) as c:
                run(c)
        except TransactionError as e:
            print(f"[1;31merror:[m {str(e)}")
        except SimpleAutomationError as e:
            print(f"[1;31merror:[m {str(e)}")
            raise e
