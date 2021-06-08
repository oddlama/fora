from .main import main

class NotYetLoaded:
    pass

"""
The inventory module we are operating on.
This is loaded from the inventory definition file (inventory.py).
"""
inventory = NotYetLoaded()

"""
The list of all instanciated host modules, after they were all loaded.
"""
hosts = NotYetLoaded()

"""
The identifier of the host that is currently active or being loaded.
This corresponds to the identifier defined via hosts list in the inventory.
"""
host_id = None

"""
The currently active host. Only set when a user script is being executed
and not while the host is being loaded.
"""
host = None

"""
A list of all loaded and unlocked vaults. Used to prevent asking multiple times to decrypt the same vault.
"""
loaded_vaults = {}

"""
The jinja2 environment used for templating
"""
jinja2_env = NotYetLoaded()
