from simple_automation.vars import Vars

def merge(source, destination):
    for key, value in source.items():
        if isinstance(value, dict):
            # get node or create one
            node = destination.setdefault(key, {})
            merge(value, node)
        else:
            destination[key] = value

    return destination


class Context:
    def __init__(self, host):
        self.host = host
        self.precomputed_vars = self._vars()

        # Remote state (context)
        self.dir_mode = 0o700
        self.file_mode = 0o600
        self.owner = "root"
        self.group = "root"
        self.umask_value = 0o077

    def defaults(self, dir_mode, file_mode, owner, group):
        self.dir_mode = dir_mode
        self.file_mode = file_mode
        self.owner = owner
        self.group = group

    def umask(self, value):
        self.umask_value = value
        # TODO set umask on connection

    def _vars(self):
        # Create merged dictionary
        d = self.host.manager.vars.copy()
        for group in self.host.groups:
            merge(group.vars, d)
        merge(self.host.vars, d)

        # Add procedural entries
        temp = Vars()
        temp.vars = d
        temp.set("context.host", self.host)
        return d

    def vars(self):
        return self.precomputed_vars
