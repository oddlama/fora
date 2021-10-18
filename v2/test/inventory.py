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
