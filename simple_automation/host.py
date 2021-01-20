from simple_automation.vars import Vars

class Host(Vars):
    def __init__(self, manager, identifier, ssh_host):
        super().__init__()
        self.manager = manager
        self.identifier = identifier
        self.ssh_host = ssh_host
        self.ssh_port = 22
        self.ssh_scp_params = []
        self.groups = []
        manager.set(f"hosts.{identifier}.ssh_host", self.ssh_host)

    def set_ssh_port(self, port):
        self.ssh_port = port

    def set_ssh_scp_params(self, params):
        self.ssh_scp_params = params

    def add_group(self, group):
        self.groups.append(group)
