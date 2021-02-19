"""
Collects the main classes for easy importing in derived scripts.
"""

from .exceptions import SimpleAutomationError, MessageError, LogicError, RemoteExecError, TransactionError
from .context import Context
from .group import Group
from .host import Host
from .manager import Manager, run_inventory
from .task import Task, TrackedTask
from .inventory import Inventory
from .vault import GpgVault, SymmetricVault
