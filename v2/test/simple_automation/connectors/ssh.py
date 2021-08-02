"""
Contains a connector which handles connections to hosts via SSH.
"""

from simple_automation import logger
from simple_automation.log import ConnectionLogger
from simple_automation.connectors.connector import Connector, connector
from simple_automation.connectors.ssh_dispatcher import Connection as SshConnection, PacketExit
from simple_automation.types import HostType

import simple_automation.connectors.ssh_dispatcher_minified

import sys
import base64
import zlib
import subprocess

from typing import Optional

@connector
class SshConnector(Connector):
    """
    A connector that provides remote access via SSH.
    """
    schema = "ssh"

    def __init__(self, url: Optional[str], host: HostType):
        super().__init__(url, host)

        self.ssh_opts: list[str] = host.ssh_opts if hasattr(host, 'ssh_opts') else []
        if url is not None and url.startswith("ssh://"):
            self.url = url
        else:
            self.url: str = f"ssh://{host.ssh_host}:{host.ssh_port}"

        self.log: ConnectionLogger = logger.new_connection(host, self)
        self.conn: SshConnection

    def open(self):
        self.log.init()
        with open(ssh_dispatcher_minified.__file__, 'rb') as f:
            ssh_dispatcher_gz_b64 = base64.b64encode(zlib.compress(f.read())).decode('ascii')

        # Start the remote ssh dispatcher by uploading it inline as base64.
        command = self._base_ssh_command(f"python3 -c \"$(echo '{ssh_dispatcher_gz_b64}' | base64 -d | gunzip)\"")
        self.process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=sys.stderr)
        self.conn = SshConnection(self.process.stdin.buffer, self.process.stdout.buffer)

        #self._check_capabilities()
        self.log.established()

    def close(self):
        PacketExit().write(self.conn)
        self.log.requested_close()
        self.process.stdin.close()
        self.process.wait()
        self.process.stdout.close()
        self.log.closed()

    def _base_ssh_command(self, remote_command_escaped):
        """
        Constructs the base ssh command using the options supplied from the respective
        host that this context is bound to.
        """
        command = ["ssh"]
        command.extend(self.ssh_opts)
        command.append(self.url)
        command.append(remote_command_escaped)
        return command
