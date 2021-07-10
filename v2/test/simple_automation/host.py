"""
This module provides all host related functionality, as well as a global
variable 'this' that may be used inside a host module to modify it's own meta
information.
"""

from types import ModuleType
from typing import Optional, Any

import simple_automation
from .types import HostType

class HostMeta:
    """
    This class represents all meta information available to a host module when itself is being loaded.
    It allows a module to access and modify its associated meta-information. After the module
    has been loaded, the meta information will be transferred directly to the module.
    """

    def __init__(self, host_id: str, loaded_from: str):
        self.name: str = host_id
        """
        The corresponding host name as defined in the inventory.
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

        self.groups: set[str] = set()
        """
        The set of groups this host belongs to.
        """

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
        self.groups.add(group)

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

    @staticmethod
    def get_variables(host: HostType) -> set[str]:
        """
        Returns the list of all user-defined attributes for a host.

        Parameters
        ----------
        host : HostType
            The host module

        Returns
        -------
        set[str]
            The user-defined attributes for the given host
        """
        host_vars = set(attr for attr in dir(host) if
                         not callable(getattr(host, attr)) and
                         not attr.startswith("_") and
                         not isinstance(getattr(host, attr), ModuleType))
        host_vars -= HostType.reserved_vars
        host_vars.remove('this')
        return host_vars

    @staticmethod
    def getattr_hierarchical(host: HostType, attr: str) -> Any:
        """
        Looks up and returns the given attribute on the host's hierarchy in the following order:
          1. Host variables
          2. Group variables (respecting topological order), the global "all" group
             implicitly will be the last in the chain
          3. Task variables
          4. raises AttributeError

        If the attribute start with an underscore, the lookup will always be from the host object
        itself, and won't be propagated.

        Parameters
        ----------
        host : HostType
            The host on which we operate
        attr : str
            The attribute to get

        Returns
        -------
        Any
            The attributes value if it was found.
        """
        if attr.startswith("_"):
            if attr not in host.__dict__:
                raise AttributeError(attr)
            return host.__dict__[attr]

        # Look up variable on host module
        if attr in host.__dict__:
            return host.__dict__[attr]

        # Look up variable on groups
        for g in simple_automation.group_order:
            # Only consider a group if the host is in that group
            if g not in host.__dict__["meta"].groups:
                continue

            # Return the attribute if it is set on the group
            group = simple_automation.groups[g]
            if hasattr(group, attr):
                return getattr(group, attr)

        # TODO task variables lookup here
        # if simple_automation.task is not None:
        #    if hasattr(simple_automation.task, attr):
        #        return getattr(simple_automation.task, attr)

        raise AttributeError(attr)

    @staticmethod
    def hasattr_hierarchical(host: HostType, attr: str) -> Any:
        """
        Checks whether the given attribute exists in the host's hierarchy.
        Checks are done in the following order:
          1. Host variables
          2. Group variables (respecting topological order), the global "all" group
             implicitly will be the last in the chain
          3. Task variables
          4. False

        If the attribute start with an underscore, the lookup will always be from the host object
        itself, and won't be propagated.

        Parameters
        ----------
        host : HostType
            The host on which we operate
        attr : str
            The attribute to check

        Returns
        -------
        bool
            True if the attribute exists
        """
        if attr.startswith("_"):
            return attr in host.__dict__

        # Look up variable on host module
        if attr in host.__dict__:
            return True

        # Look up variable on groups
        for g in simple_automation.group_order:
            # Only consider a group if the host is in that group
            if g not in host.__dict__["meta"].groups:
                continue

            # Return the attribute if it is set on the group
            group = simple_automation.groups[g]
            if hasattr(group, attr):
                return True

        # TODO task variables lookup here
        # if simple_automation.task is not None:
        #    if hasattr(simple_automation.task, attr):
        #        return True

        return False

this: Optional[HostMeta] = None
"""
This variable holds all meta information available to a host module when itself is being loaded.
This variable should only ever be used in the context of a host module as shown below, otherwise
it will be None.

It allows the module to access meta-variables about itself, such as the host's name
that has been used to instanciate it in the inventory. It also allows modification of these
meta properties, such as which groups it should belong to, or what ssh settings should
be used for connections.

When writing a host module, you can simply import :attr:`simple_automation.host.this`,
which exposes an API to access/modify this information.

.. topic:: Example: Using meta information (hosts/myhost.py)

    .. code-block:: python

        from simple_automation.host import this

        # The host name used for instanciation as defined in the inventory
        print(this.name)

        # Set the ssh host (useful if it differs from the name)
        this.ssh_host = "root@localhost"

        # Add the host to a group
        this.add_group("desktops")
"""
