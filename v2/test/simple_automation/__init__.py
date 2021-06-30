from typing import Optional, Union
from types import ModuleType

class NotYetLoaded:
    pass

"""
The inventory module we are operating on.
This is loaded from the inventory definition file (inventory.py).
"""
inventory = NotYetLoaded()

"""
The list of all group modules loaded from groups/*.py.
"""
groups: dict[str, ModuleType] = NotYetLoaded()

"""
A topological order of all groups
"""
group_order = NotYetLoaded()

"""
The list of all instanciated host modules, after they were all loaded.
"""
hosts = NotYetLoaded()

"""
The list of all loaded task modules.
"""
tasks = NotYetLoaded()

"""
The identifier of the host that is currently active or being loaded.
This corresponds to the identifier defined via hosts list in the inventory.
"""
host_id: Optional[str] = None

"""
The currently active host. Only set when a user script is being executed
and not while the host is being loaded.
"""
host = None

"""
A list of all loaded and unlocked vaults. Used to prevent asking multiple times to decrypt the same vault.
"""
# TODO dict[str, Vault]
loaded_vaults: dict[str, int] = {}

"""
The jinja2 environment used for templating
"""
jinja2_env = NotYetLoaded()
