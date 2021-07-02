from typing import Optional

class HostMeta:
    """
    This class represents all meta information available to a host module when itself is being loaded.
    It allows a module to access and modify its associated meta-information.
    """

    def __init__(self, host_id):
        self.id = host_id
        """
        The corresponding host id as defined in the inventory.
        """

        self.groups = set()

    def add_group(self, group):
        self.groups.add(group)

    def add_groups(self, groups):
        self.groups.update(groups)

this: Optional[HostMeta] = None
"""
This variable holds all meta information available to a host module when itself is being loaded.
This variable should only ever be used in the context of a host module as shown below, otherwise
it will be None.

It allows the module to access meta-variables about itself, such as the host's id
that has been used to instanciate it in the inventory. It also allows modification of these
meta properties, such as which groups it should belong to, or what ssh settings should
be used for connections.

When writing a host module, you can simply import :attr:`simple_automation.host.this`,
which exposes an API to access/modify this information.

.. topic:: Example: Using meta information (hosts/myhost.py)

    .. code-block:: python

        from simple_automation.host import this

        # The host id used for instanciation as defined in the inventory
        print(this.id)

        # Set the ssh host (useful if it differs from the id)
        this.ssh_host("root@localhost")

        # Add the host to a group
        this.add_group("desktops")
"""
