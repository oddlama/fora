from simple_automation.vars import Vars
from simple_automation.remote_exec import script_path as local_remote_exec_script_path

import subprocess
from subprocess import CalledProcessError
import os

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

    def __enter__(self):
        # Initialize ssh environment
        self.init_ssh()
        return self

    def __exit__(self, type, value, traceback):
        # Remove temporary files, and also do a safety check in
        # case anything goes horribly wrong.
        if self.remote_temp_dir.startswith("/tmp"):
            self.exec_ssh_raw(["rm", "-rf", self.remote_temp_dir])

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

    def _base_ssh_command(self, command):
        ssh_command = ["ssh"]
        ssh_command.extend(self.host.ssh_scp_params)
        ssh_command.append(f"ssh://{self.host.ssh_host}:{self.host.ssh_port}")
        ssh_command.extend(command)
        return ssh_command

    def _base_scp_command(self, local_path, remote_path, recursive=False):
        scp_command = ["scp"]
        if recursive:
            scp_command.append("-r")
        scp_command.extend(self.host.ssh_scp_params)
        scp_command.append(local_path)
        scp_command.append(f"scp://{self.host.ssh_host}:{self.host.ssh_port}/{remote_path}")
        return scp_command

    def init_ssh(self):
        """
        Initialize environment on the remote host (temporary directory, remote exec script),
        so we can more easily execute commands on the remote.
        """
        print(f"Establishing ssh connection to {self.host.ssh_host}")
        # Create temporary directory
        self.remote_temp_dir = self.exec_ssh_raw(["mktemp", "-d"]).stdout.decode("utf-8").split('\n')[0]
        # Upload exec script
        self.remote_exec_script_path = self.upload_file(local_remote_exec_script_path)

    def exec_ssh_raw(self, command):
        """
        Execute ssh to execute the given command on the remote host, directly via ssh.
        """
        return subprocess.run(self._base_ssh_command(command), check=True, capture_output=True)

    def exec_ssh(self, command):
        """
        Execute ssh to execute the given command on the remote host
        """
        # Execute the remote execution script and pass our command parameters
        # NUL-terminated later so we don't have to worry about any quoting.
        # This therefore ensures that there is no command injection possible.
        return subprocess.run(self._base_ssh_command([self.remote_exec_script_path]), capture_output=True)

        # TODO pass meta settings
        # TODO pass command
        # TODO timeout

    def upload_file(self, file):
        """
        Uploads the given file to the temporary directory on the remote host
        and returns the absolute path to the resulting file.
        """
        basename = os.path.basename(file)
        remote_file_path = os.path.join(self.remote_temp_dir, basename)
        subprocess.run(self._base_scp_command(file, remote_file_path), check=True)
        return remote_file_path

    def remote_exec(self, command):
        """
        Executes a command on the remote host, respecting all the default state given in here
        """
        self.exec_ssh(command, become=True)
