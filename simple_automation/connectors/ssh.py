"""
Contains a connector which handles connections to hosts via SSH.
"""

import sys
import base64
import zlib
import subprocess

from typing import Optional

import simple_automation
import simple_automation.connectors.tunnel_dispatcher as td

from simple_automation import logger
from simple_automation.connectors.connector import Connector, connector, CompletedRemoteCommand, StatResult
from simple_automation.log import ConnectionLogger
from simple_automation.types import HostType
from simple_automation.utils import AbortExecutionSignal

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
        self.process: Optional[subprocess.Popen] = None
        self.conn: td.Connection
        self.is_open: bool = False

    def _expect_response_packet(self, packet, expected_type):
        if not isinstance(packet, expected_type):
            self.log.error(f"Invalid response '{type(packet)}'")
            raise RuntimeError(f"Invalid response '{type(packet)}' from remote dispatcher. This is a bug.")

    def open(self):
        self.log.init()
        with open(td.__file__, 'rb') as f:
            tunnel_dispatcher_gz_b64 = base64.b64encode(zlib.compress(f.read(), 9)).decode('ascii')

        # Start the remote dispatcher by uploading it inline as base64
        param_debug = "--debug" if simple_automation.args.debug else ""
        command = self._ssh_command(f"env python3 -c \"$(echo '{tunnel_dispatcher_gz_b64}' | base64 -d | openssl zlib -d)\" {param_debug}")
        self.process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=sys.stderr)
        self.conn = td.Connection(self.process.stdout, self.process.stdin)

        try:
            self.conn.write_packet(td.PacketCheckAlive())
            packet = td.receive_packet(self.conn)
            if packet is not None and not isinstance(packet, td.PacketAck):
                raise RuntimeError("Invalid response from remote dispatcher. This is a bug.")

            # As a last action record that the connection is opened successfully,
            # otherwise the finally block will kill the process.
            self.is_open = True
        except IOError as e:
            returncode = self.process.poll()
            if returncode is None:
                self.log.failed(f"Dispatcher handshake failed: {str(e)}")
            else:
                self.log.failed(f"Dispatcher handshake failed: ssh exited with code {returncode}")
            raise AbortExecutionSignal() from e
        finally:
            # If the connection failed for any reason, be sure to kill the background process.
            if not self.is_open:
                self.process.terminate()
                self.process = None

        self.log.established()

        # TODO assert Popen proccess is killed atexit
        #self._check_capabilities()
        # TODO check that we are root.

    def close(self):
        if self.is_open:
            self.conn.write_packet(td.PacketExit())
            self.log.requested_close()

        if self.process is not None:
            if self.process.stdin is not None:
                self.process.stdin.close()
            self.process.wait()
            if self.process.stdout is not None:
                self.process.stdout.close()
            self.process = None
            self.log.closed()

    def run(self,
            command: list[str],
            input: Optional[bytes] = None, # pylint: disable=redefined-builtin
            capture_output: bool = True,
            check: bool = True,
            user: Optional[str] = None,
            group: Optional[str] = None,
            umask: Optional[str] = None,
            cwd: Optional[str] = None) -> CompletedRemoteCommand:
        try:
            # Construct and send packet with process information
            packet_run = td.PacketProcessRun(
                command=command,
                stdin=input,
                capture_output=capture_output,
                user=user,
                group=group,
                umask=umask,
                cwd=cwd)
            self.conn.write_packet(packet_run)

            # Wait for result packet
            packet = td.receive_packet(self.conn)
        except IOError as e:
            self.log.error(f"Remote host disconnected unexpectedly: {str(e)}")
            raise AbortExecutionSignal() from e

        # Check type of incoming packet to handle errors differently
        if isinstance(packet, td.PacketInvalidField):
            raise ValueError(f"Invalid value '{getattr(packet_run, packet.field)}' given for field '{packet.field}': {packet.error_message}")

        if not isinstance(packet, td.PacketProcessCompleted):
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

    def stat(self, path: str, follow_links: bool = False, sha512sum: bool = False) -> Optional[StatResult]:
        try:
            # Construct and send packet with process information
            packet_stat = td.PacketStat(
                path=path,
                follow_links=follow_links,
                sha512sum=sha512sum)
            self.conn.write_packet(packet_stat)

            # Wait for result packet
            packet = td.receive_packet(self.conn)
        except IOError as e:
            self.log.error(f"Remote host disconnected unexpectedly: {str(e)}")
            raise AbortExecutionSignal() from e

        # Check type of incoming packet to handle errors
        if isinstance(packet, td.PacketInvalidField):
            return None

        self._expect_response_packet(packet, td.PacketStatResult)
        return StatResult(
            type=packet.type,
            mode=packet.mode,
            owner=packet.owner,
            group=packet.group,
            size=packet.size,
            mtime=packet.mtime,
            ctime=packet.ctime,
            sha512sum=packet.sha512sum)

    def resolve_user(self, user: Optional[str]) -> Optional[str]:
        if user is None:
            return None

        try:
            packet_resolve = td.PacketResolveUser(user=user)
            self.conn.write_packet(packet_resolve)

            # Wait for result packet
            packet = td.receive_packet(self.conn)
        except IOError as e:
            self.log.error(f"Remote host disconnected unexpectedly: {str(e)}")
            raise AbortExecutionSignal() from e

        # Check type of incoming packet to handle errors differently
        if isinstance(packet, td.PacketInvalidField):
            raise ValueError(f"User '{user}' doesn't exist")

        self._expect_response_packet(packet, td.PacketResolveResult)
        return packet.value

    def resolve_group(self, group: Optional[str]) -> Optional[str]:
        if group is None:
            return None

        try:
            packet_resolve = td.PacketResolveGroup(group=group)
            self.conn.write_packet(packet_resolve)

            # Wait for result packet
            packet = td.receive_packet(self.conn)
        except IOError as e:
            self.log.error(f"Remote host disconnected unexpectedly: {str(e)}")
            raise AbortExecutionSignal() from e

        # Check type of incoming packet to handle errors differently
        if isinstance(packet, td.PacketInvalidField):
            raise ValueError(f"Group '{group}' doesn't exist")

        self._expect_response_packet(packet, td.PacketResolveResult)
        return packet.value

    def upload(self,
            file: str,
            content: bytes,
            mode: Optional[str] = None,
            owner: Optional[str] = None,
            group: Optional[str] = None):
        try:
            packet_upload = td.PacketUpload(
                    file=file,
                    content=content,
                    mode=mode,
                    owner=owner,
                    group=group)
            self.conn.write_packet(packet_upload)

            # Wait for result packet
            packet = td.receive_packet(self.conn)
        except IOError as e:
            self.log.error(f"Remote host disconnected unexpectedly: {str(e)}")
            raise AbortExecutionSignal() from e

        # Check type of incoming packet to handle errors differently
        if isinstance(packet, td.PacketInvalidField):
            raise ValueError(f"Invalid value '{getattr(packet_upload, packet.field)}' given for field '{packet.field}': {packet.error_message}")

        self._expect_response_packet(packet, td.PacketOk)

    def download(self, file: str) -> bytes:
        try:
            packet_download = td.PacketDownload(file=file)
            self.conn.write_packet(packet_download)

            # Wait for result packet
            packet = td.receive_packet(self.conn)
        except IOError as e:
            self.log.error(f"Remote host disconnected unexpectedly: {str(e)}")
            raise AbortExecutionSignal() from e

        # Check type of incoming packet to handle errors differently
        if isinstance(packet, td.PacketInvalidField):
            raise ValueError(f"Invalid value '{getattr(packet_download, packet.field)}' given for field '{packet.field}': {packet.error_message}")

        self._expect_response_packet(packet, td.PacketDownloadResult)
        return packet.content

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
