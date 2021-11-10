"""
Provides api for host definitions.
"""

from typing import cast

# TODO make Example a section in the sphinx documentation
class HostType(MockupType):
    """
    A mockup type for host modules. This is not the actual type of an instanciated
    module, but will reflect some of it's properties better than ModuleType.

    This class also represents all meta information available to a host module when itself is being loaded.
    It allows a module to access and modify its associated meta-information. After the module
    has been loaded, the meta information will be transferred directly to the module.

    When writing a host module, you can simply import :attr:`simple_automation.host.this`,
    which exposes an API to access/modify this information.

    Example: Using meta information (hosts/myhost.py)

    .. code-block:: python

        from simple_automation.host import this

        # The host name used for instanciation as defined in the inventory
        print(this.name)

        # Set the ssh host (useful if it differs from the name)
        this.ssh_host = "root@localhost"

        # Add the host to a group
        this.add_group("desktops")
    """

    reserved_vars: set[str] = set(["module", "name", "loaded_from", "groups", "url", "connector", "connection"])
    """
    A list of variable names that are reserved and must not be set by the module.
    """

    def __init__(self, host_id: str, loaded_from: str):
        self.module: ModuleType
        """
        The associated dynamically loaded module (will be set before the dynamic module is executed).
        """

        self.name: str = host_id
        """
        The corresponding host name as defined in the inventory.
        Must not be changed.
        """

        self.loaded_from: str = loaded_from
        """
        The original file path of the instanciated module.
        """

        self.groups: set[str] = set()
        """
        The set of groups this host belongs to.
        """

        self.url: str = "ssh:"
        """
        The url to the host. A matching connector for the schema must exist.
        Defaults to an ssh connection if unset. Connection details can be given in the url
        or via attributes on the host module.
        """

        self.connector: Optional[Callable[[str, HostType], Connector]] = None
        """
        The connector class to use. If unset the connector will be determined by the url.
        """

        self.connection: Connection = cast("Connection", None) # Cast None to ease typechecking in user code.
        """
        The connection to this host, if it is opened.
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
    def getattr_hierarchical(host: HostType, attr: str) -> Any:
        """
        Looks up and returns the given attribute on the host's hierarchy in the following order:
          1. Host variables
          2. Group variables (respecting topological order), the global "all" group
             implicitly will be the last in the chain
          3. Script variables
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
            if g not in host.__dict__["groups"]:
                continue

            # Return the attribute if it is set on the group
            group = simple_automation.groups[g]
            if hasattr(group, attr):
                return getattr(group, attr)

        # Look up variable on current script
        if isinstance(simple_automation.script.this, ScriptType):
            if hasattr(simple_automation.script.this.module, attr):
                return getattr(simple_automation.script.this.module, attr)

        raise AttributeError(attr)

    @staticmethod
    def hasattr_hierarchical(host: HostType, attr: str) -> Any:
        """
        Checks whether the given attribute exists in the host's hierarchy.
        Checks are done in the following order:

           1. Host variables
           2. Group variables (respecting topological order), the global "all" group
              implicitly will be the last in the chain
           3. Script variables
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
            if g not in host.__dict__["groups"]:
                continue

            # Return the attribute if it is set on the group
            group = simple_automation.groups[g]
            if hasattr(group, attr):
                return True

        # Look up variable on current script
        if isinstance(simple_automation.script.this, ScriptType):
            if hasattr(simple_automation.script.this.module, attr):
                return True

        return False

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
        return _get_variables(HostType, host)

this: HostType = cast(HostType, None) # Cast None to ease typechecking in user code.
"""
This variable holds all meta information available to a host module when
it is being loaded. It must not be used anywhere else but inside the
definition (source) of the actual module.
"""
