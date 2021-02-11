from simple_automation.host import Host
from simple_automation.vars import Vars

class Group(Vars):
    def __init__(self, manager, identifier):
        super().__init__()
        self.manager = manager
        self.identifier = identifier

    def __contains__(self, host):
        if not isinstance(host, Host):
            raise ValueError(f"Expected Host, got {type(host)}")
        return self in host.groups
