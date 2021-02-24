"""
Provides the host class.
"""

from simple_automation.vars import Vars

class Host(Vars):
    """
    A Host represents a machine that can be reached via ssh, and
    which should be managed by simple_automation.
    It can store variables which override gloabl and group variables,
    which may be used to customize the execution routine.
    """

    def __init__(self, manager, identifier, ssh_host):
        """
        Initializes a new host.
        """
        super().__init__()
        self.manager = manager
        self.identifier = identifier
        self.ssh_host = ssh_host
        self.ssh_port = 22
        self.ssh_opts = []
        self.groups = []

    def set_ssh_port(self, port):
        """
        Sets the ssh port for the host's connection.

        Parameters
        ----------
        port : int
            The port number to connect to
        """
        self.ssh_port = port

    def set_ssh_opts(self, opts):
        """
        Sets additional ssh parameters for this host's connection.

        Parameters
        ----------
        opts : list[string]
            Additional parameters to ssh
        """
        self.ssh_opts = opts

    def add_group(self, group):
        """
        Adds this host to the given group, if it isn't already in that group.
        """
        if self not in group:
            self.groups.append(group)
