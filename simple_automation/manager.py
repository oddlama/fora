from simple_automation.version import __version__
from simple_automation.group import Group
from simple_automation.host import Host
from simple_automation.task import Task
from simple_automation.context import Context
from simple_automation.exceptions import SimpleAutomationError, TransactionError
from simple_automation.vars import Vars

from jinja2 import Environment, FileSystemLoader

import argparse

class ArgumentParserError(Exception):
    pass

class ThrowingArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        raise ArgumentParserError(message)

class Manager(Vars):
    def __init__(self, main_directory):
        super().__init__()
        self.groups = {}
        self.hosts = {}
        self.tasks = {}
        self.main_directory = main_directory
        self.jinja2_env = Environment(
            loader=FileSystemLoader(self.main_directory, followlinks=True),
            autoescape=False)
        self.set("simple_automation_managed", "This file is managed by simple automation.")

    def add_group(self, identifier):
        group = Group(self, identifier)
        if identifier in self.groups:
            raise Exception(f"Cannot register group: Duplicate identifier {identifier}")
        self.groups[identifier] = group
        return group

    def add_host(self, identifier, ssh_host):
        host = Host(self, identifier, ssh_host)
        if identifier in self.hosts:
            raise Exception(f"Cannot register host: Duplicate identifier {identifier}")
        self.hosts[identifier] = host
        return host

    def add_task(self, task_class):
        identifier = task_class.identifier
        if identifier in self.tasks:
            raise Exception(f"Cannot register task: Duplicate identifier {identifier}")
        task = task_class(self)
        self.tasks[identifier] = task
        return task

    def main(self, run):
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

        # TODO ask for vault key, vaultdecrypt = ask = [openssl - ...], gpg = []
        # TODO ask for su key, becomekey=ask,command=[]
        # TODO becomemethod=su, sudo -u root, ...
        try:
            with Context(self.hosts["my_laptop"],
                         pretend=args.pretend,
                         verbose=args.verbose,
                         debug=args.debug) as c:
                run(c)
        except TransactionError as e:
            print(f"[1;31merror:[m {str(e)}")
        except SimpleAutomationError as e:
            print(f"[1;31merror:[m {str(e)}")
            raise e
