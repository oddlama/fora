class Host:
    def __init__(self, manager, identifier, ssh_host):
        self.identifier = identifier
        self.ssh_host = ssh_host
        manager.set(f"hosts.{identifier}.ssh_host", self.ssh_host)

    def get(self, context, var):
        # TODO: get variable from our dictionary,
        # then fall back to group dictionary, then
        # fallback to manager's dictionary
        pass

    def set(self, context, var, val):
        pass
