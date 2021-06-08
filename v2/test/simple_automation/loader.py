"""
Provides the submodule loading functions.
"""

import simple_automation
import glob
import os
from simple_automation.utils import die_error, load_py_module

def load_group(module_file: str):
    ret = load_py_module(module_file)
    ret.name = os.path.splitext(os.path.basename(module_file))[0]
    return ret

def load_host(host_id: str, module_file: str):
    simple_automation.host_id = host_id
    ret = load_py_module(module_file)
    simple_automation.host_id = None

    ret.id = host_id
    if not hasattr(ret, 'ssh_host'):
        die_error(f"{module_file}: ssh_host not defined!")
    if not hasattr(ret, 'groups'):
        ret.groups = []
    else:
        for group in ret.groups:
            if group not in simple_automation.groups:
                die_error(f"{module_file}: Invalid group '{group}' or missing definition groups/{group}.py!")

    # Add all hosts to the group "all", and deduplicate the groups list.
    ret.groups = list(set(ret.groups + ["all"]))

    return ret

def load_inventory():
    simple_automation.inventory = load_py_module('inventory.py')
    if not hasattr(simple_automation.inventory, 'hosts'):
        die_error("inventory.py: inventory must define a list of hosts!")
    if not isinstance(simple_automation.inventory.hosts, list):
        die_error("inventory.py: hosts variable must be a list!")

def load_groups():
    # Load all groups defined in groups/
    loaded_groups = {}
    for file in glob.glob('groups/*.py'):
        group = load_group(file)
        loaded_groups[group.name] = group

    # Create default all group if it wasn't defined
    if 'all' not in loaded_groups:
        loaded_groups['all'] = { 'name': 'all' }

    simple_automation.groups = loaded_groups

def sort_groups():
    # TODO
    pass

def load_hosts():
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
    simple_automation.hosts = loaded_hosts

def load_tasks():
    pass

def load_site():
    # Load the inventory
    load_inventory()

    # Load all groups from groups/*.py
    load_groups()
    # Sort groups respecting their defined dependencies
    sort_groups()

    # Load all hosts defined in the inventory
    load_hosts()

    # Load all tasks recursively from tasks/
    load_tasks()
