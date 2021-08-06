"""
Contains a connector which handles connections to hosts via SSH.
"""

import sys
import base64
import zlib
import subprocess

from typing import Optional

import simple_automation.connectors.tunnel_dispatcher_minified

from simple_automation import logger
from simple_automation.log import ConnectionLogger
from simple_automation.connectors.connector import Connector, connector, CompletedRemoteCommand
from simple_automation.connectors.tunnel_dispatcher import Connection as SshConnection, PacketExit, PacketCheckAlive, PacketAck, PacketProcessRun, PacketProcessCompleted, PacketInvalidField, receive_packet
from simple_automation.types import HostType

@connector
class SshConnector(Connector):
    """
    A connector that provides remote access via SSH.
    """
    schema = "ssh"

    def __init__(self, url: Optional[str], host: HostType):
        super().__init__(url, host)

        self.ssh_opts: list[str] = getattr(host, 'ssh_opts') if hasattr(host, 'ssh_opts') else []
        if url is not None and url.startswith("ssh://"):
            self.url = url
        else:
            self.url: str = f"ssh://{getattr(host, 'ssh_host')}:{getattr(host, 'ssh_port')}"

        self.log: ConnectionLogger = logger.new_connection(host, self)
        self.process: subprocess.Popen
        self.conn: SshConnection

    def open(self):
        self.log.init()
        with open(simple_automation.connectors.tunnel_dispatcher_minified.__file__, 'rb') as f:
            tunnel_dispatcher_gz_b64 = base64.b64encode(zlib.compress(f.read(), 9)).decode('ascii')

        # Start the remote dispatcher by uploading it inline as base64.
        command = self._ssh_command(f"env python3 -c \"$(echo '{tunnel_dispatcher_gz_b64}' | base64 -d | openssl zlib -d)\"")
        self.process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=sys.stderr)
        self.conn = SshConnection(self.process.stdout, self.process.stdin)
        try:
            PacketCheckAlive().write(self.conn)
            packet = receive_packet(self.conn)
            if packet is not None and not isinstance(packet, PacketAck):
                raise RuntimeError("Invalid response from remote dispatcher. This is a bug.")
        except IOError as e:
            self.log.failed("Dispatcher handshake failed")
            raise IOError("Failed to establish connection to remote host.") from e

        self.log.established()

        # TODO assert Popen proccess is killed atexit
        #self._check_capabilities()
        # TODO check that we are root.

    def close(self):
        PacketExit().write(self.conn)
        self.log.requested_close()
        self.process.stdin.close()
        self.process.wait()
        self.process.stdout.close()
        self.log.closed()

    def run(self, command: list[str],
            input: Optional[bytes], # pylint: disable=redefined-builtin
            capture_output: bool,
            check: bool,
            user: Optional[str],
            group: Optional[str],
            umask: Optional[str],
            cwd: Optional[str]) -> CompletedRemoteCommand:
        try:
            # Construct and send packet with process information
            packet_run = PacketProcessRun(
                command=command,
                stdin=input,
                capture_output=capture_output,
                user=user,
                group=group,
                umask=umask,
                cwd=cwd)
            packet_run.write(self.conn)

            # Wait for result packet
            packet = receive_packet(self.conn)
        except IOError as e:
            self.log.error("Unexpected EOF")
            raise IOError("Remote host disconnected unexpectedly.") from e

        # Check type of incoming packet to handle errors differently
        if isinstance(packet, PacketInvalidField):
            raise ValueError(f"Invalid value '{getattr(packet_run, packet.field)}' given for field '{packet.field}': {packet.error_message}")

        if not isinstance(packet, PacketProcessCompleted):
            self.log.error(f"Invalid response '{type(packet)}'")
            raise RuntimeError(f"Invalid response '{type(packet)}' from remote dispatcher. This is a bug.")

        result = CompletedRemoteCommand(stdout=packet.stdout,
                                        stderr=packet.stderr,
                                        returncode=packet.returncode)

        # Check output if requested
        if check and result.returncode != 0:
            raise subprocess.CalledProcessError(returncode=result.returncode,
                                                output=result.stdout,
                                                stderr=result.stderr,
                                                cmd=command)

        return result

    def _ssh_command(self, remote_command_escaped: str) -> list[str]:
        """
        Constructs the ssh command needed to execute the given
        escaped command on the remote host.

        Parameters
        ----------
        remote_command_escaped
            The fully excaped program that should be appended to the ssh command.

        Returns
        -------
        list[str]
            The complete ssh command.
        """
        command = ["ssh"]
        command.extend(self.ssh_opts)
        command.append(self.url)
        command.append(remote_command_escaped)
        return command