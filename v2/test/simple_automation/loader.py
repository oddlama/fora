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

def load_site():
    # Load the inventory
    load_inventory()

    # Load all hosts defined in the inventory
    loaded_hosts = []
    for host in simple_automation.inventory.hosts:
        if isinstance(host, str):
            loaded_hosts.append(load_host(host_id=host, module_file=f"hosts/{host}.py"))
        elif isinstance(host, tuple):
            (name, module_py) = host
            loaded_hosts.append(load_host(name=name, module_file=module_py))
        else:
            die_error(f"inventory.py: invalid host '{str(host)}'")
    simple_automation.inventory.hosts = loaded_hosts

    # Load all groups from groups/*.py
    # TODO
