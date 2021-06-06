"""
Provides all inventory related functionality.
"""

# TODO
"""
Defines a new host.

A host represents a machine that can be reached via ssh,
which can then be managed by simple_automation.

Parameters
----------
name : str
    A unique identifier for the host.
ssh_host : str
    The ssh destination address
ssh_port : int
    The port number to connect to
ssh_opts : list[str]
    Additional parameters to ssh
host_vars: str
    List of groups this host belongs to
groups : list[str]
    List of groups this host belongs to
"""
