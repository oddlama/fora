"""
Provides the submodule loading functions.
"""

import simple_automation
from simple_automation.utils import die_error, load_py_module

def load_host(host_id: str, module_file: str):
    simple_automation.host_id = host_id
    ret = load_py_module(module_file)
    simple_automation.host_id = None

    ret.id = host_id
    if not hasattr(ret, 'ssh_host'):
        die_error(f"{module_file}: ssh_host not defined!")
    if not hasattr(ret, 'groups'):
        ret.groups = []

    return ret

def load_inventory():
    simple_automation.inventory = load_py_module('inventory.py')
    if not hasattr(simple_automation.inventory, 'hosts'):
        die_error("inventory.py: inventory must define a list of hosts!")
    if not isinstance(simple_automation.inventory.hosts, list):
        die_error("inventory.py: hosts variable must be a list!")
