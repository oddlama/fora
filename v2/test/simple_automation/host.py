import simple_automation

from typing import Optional

class HostMeta:
    """
    This class represents all meta information available to a host module when itself is being loaded.
    It allows a module to access and modify its associated meta-information.
    """

    def __init__(self, host_id: str, loaded_from: str):
        self.id: str = host_id
        """
        The corresponding host id as defined in the inventory.
        Must not be changed.
        """

        self.loaded_from: str = loaded_from
        """
        The original file path of the instanciated module.
        """

        self.ssh_host: str = host_id
        """
        The ssh destination as accepted by ssh(1).
        """

        self.ssh_port: int = 22
        """
        The port used to for ssh connections.
        """

        self.ssh_opts: list[str] = []
        """
        Additional options to the ssh command for this host.
        """

        self._groups: set[str] = set()

    def add_group(self, group: str):
        """
        Adds a this host to the specified group.

        Parameters
        ----------
        group : str
            The group
        """
        if group not in simple_automation.groups:
            raise ValueError(f"Referenced invalid group '{group}'!")
        self._groups.add(group)

    def add_groups(self, groups: list[str]):
        """
        Adds a this host to the specified list of groups.

        Parameters
        ----------
        groups : list[str]
            The groups
        """
        for g in groups:
            self.add_group(g)

    def groups(self):
        """
        Returns the set of groups this host belongs to.

        Returns
        -------
        set[str]
            The set of groups this host belongs to
        """
        return self._groups

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
        this.ssh_host = "root@localhost"

        # Add the host to a group
        this.add_group("desktops")
"""
