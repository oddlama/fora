# Hosts are tuples of (name, host_definition_file) where host_definition_file is the
# python module that will be instanciated for the host, or just a name, in which case the
# instanciated module will default to "hosts/{name}.py".
#
# The instanciated module has access to the name of the host via simple_automation.host_definition.name
# and may adapt it's behavior dynamically based on this information.
hosts = [ "localhost"
#        , ("mail1", "hosts/mail.py")
#        , ("mail2", "hosts/mail.py")
        ]

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
