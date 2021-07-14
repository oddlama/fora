"""
Contains a connector which handles connections to hosts via SSH.
"""

from .base import Connector

class SshConnector(Connector):
    """
    A connector that provides remote access via SSH.
    """

    def __init__(self, host):
        super().__init__(host)

    def open(self):
        print(f"[[32m>[m] Establishing ssh connection to {self.host.ssh_host}")
        with open(local_remote_dispatch_script_path, 'rb') as f:
            remote_dispatcher_script_source_base64 = base64.b64encode(f.read()).decode('utf-8')
        # Upload and start remote dispatch script
        self.remote_dispatcher = RemoteDispatcher(self, self._base_ssh_command([f"python3 -c \"$(echo '{remote_dispatcher_script_source_base64}' | base64 -d)\""]))

    def close(self):
        self.remote_dispatcher.stop_and_wait()

    def _base_ssh_command(self, command):
        """
        Constructs the base ssh command using the options supplied from the respective
        host that this context is bound to.
        """
        ssh_command = ["ssh"]
        ssh_command.extend(self.host.ssh_opts)
        if self.host.ssh_host.startswith("ssh://"):
            ssh_command.append(self.host.ssh_host)
        else:
            ssh_command.append(f"ssh://{self.host.ssh_host}:{self.host.ssh_port}")
        ssh_command.extend(command)
        return ssh_command
