class Host:
    def __init__(self, manager, identifier, ssh_host):
        self.manager = manager
        self.identifier = identifier
        self.ssh_host = ssh_host
        self.groups = []
        manager.set(f"hosts.{identifier}.ssh_host", self.ssh_host)

    def add_group(self, group):
        self.groups.append(group)

    def get(self, context, var):
        # TODO: get variable from our dictionary,
        # then fall back to group dictionary, then
        # fallback to manager's dictionary
        pass

    def set(self, var, val):
        pass
