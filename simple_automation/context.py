from simple_automation.vars import Vars
from simple_automation.remote_exec import script_path as local_remote_exec_script_path

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

        # Initialize ssh environment
        self.init_ssh()

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

    def _base_ssh_command(self):
        return ["ssh"] + self.host.ssh_params + [self.host.ssh_host]

    def init_ssh(self):
        """
        Initialize environment on the remote host (temporary directory, remote exec script),
        so we can more easily execute commands on the remote.
        """
        # Create temporary directory
        self.remote_temp_dir = self.exec_ssh_raw(["mktemp", "-d"]).stdout_lines[0]
        # Upload exec script
        self.remote_exec_script_path = self.upload_file(local_remote_exec_script_path)

    def exec_ssh_raw(self, command):
        """
        Execute ssh to execute the given command on the remote host, directly via ssh.
        """
        return subprocess.run(self._base_ssh_command() + command, capture_output=True)

    def exec_ssh(self, command):
        """
        Execute ssh to execute the given command on the remote host
        """
        # Execute the remote execution script and pass our command parameters
        # NUL-terminated later so we don't have to worry about correct quoting.
        # This ensures that there is no command injection possible.
        return subprocess.run(self._base_ssh_command() + [self.remote_exec_script_path], capture_output=True)
        # TODO pass meta settings
        # TODO pass command
        # TODO timeout

    def upload_file(self, file):
        """
        Uploads the given file to the host and returns the absolute path to the resulting file.
        """
        return self.remote_exec(["mktemp", "-d"]).stdout_lines[0]

    def remote_exec(self, command):
        """
        Executes a command on the remote host, respecting all the default state given in here
        """
        self.exec_ssh(command, become=True)
