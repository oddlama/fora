from simple_automation.vars import Vars

def _merge(source, destination):
    for key, value in source.items():
        if isinstance(value, dict):
            # get node or create one
            node = destination.setdefault(key, {})
            _merge(value, node)
        else:
            destination[key] = value

    return destination


class Context:
    def __init__(self, host):
        self.host = host
        self.precomputed_vars = self._vars()

        # Defaults for remote actions
        self.defaults(user="root", umask=0o022, dir_mode=0o700, file_mode=0o600, owner="root", group="root")

    def defaults(self, user, umask, dir_mode, file_mode, owner, group):
        self.user(user)
        self.umask(umask)
        self.mode(dir_mode, file_mode, owner, group)

    def mode(self, dir_mode, file_mode, owner, group):
        self.dir_mode = dir_mode
        self.file_mode = file_mode
        self.owner = owner
        self.group = group

    def umask(self, value):
        self.umask_value = value

    def user(self, user):
        self.as_user = user

    def _vars(self):
        # Create merged dictionary
        d = self.host.manager.vars.copy()
        for group in self.host.groups:
            _merge(group.vars, d)
        _merge(self.host.vars, d)

        # Add procedural entries
        temp = Vars()
        temp.vars = d
        temp.set("context.host", self.host)
        return d

    def vars(self):
        return self.precomputed_vars

    def remote_upload_file(self, file):
        self.remote_exec(["mktemp", "-d"])
        """
        scp blah /tmp/simple_automation
        """

    def remote_exec(self, command):
        """
        Executes a command on the remote host, respecting all the default state given in here
        """
