"""
Provides the group class.
"""

from simple_automation.host import Host
from simple_automation.vars import Vars

class Group(Vars):
    """
    A group for hosts. Can store variables which will have higher precedence than
    global variables, but lower than host variables.
    """

    def __init__(self, manager, identifier):
        """
        Initializes a new group.
        """
        super().__init__()
        self.manager = manager
        self.identifier = identifier

    def __contains__(self, host):
        """
        Returns true if the given host belongs to this group.
        Raises a ValueError if the given object is not a Host.
        """
        if not isinstance(host, Host):
            raise ValueError(f"Expected Host, got {type(host)}")
        return self in host.groups
