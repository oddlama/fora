"""
Collects the main classes for easy importing in derived scripts.
"""

from .exceptions import SimpleAutomationError, LogicError, RemoteExecError
from .context import Context
from .group import Group
from .host import Host
from .manager import Manager
from .task import Task, TrackedTask
from .inventory import Inventory
from .vault import GpgVault, SymmetricVault

def run_inventory(inventory_class):
    """
    Instanciates a manager given an inventory class and runs the manager's CLI.
    """
    Manager(inventory_class).main()
