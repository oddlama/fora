"""Contains a connector which handles connections to hosts via SSH."""

import sys
import base64
import zlib
import subprocess
from typing import Any, Optional, Type

from simple_automation import globals as G, logger
from simple_automation.connectors import tunnel_dispatcher as td
from simple_automation.connectors.connector import CompletedRemoteCommand, Connector, StatResult, connector
from simple_automation.types import HostType

def _expect_response_packet(packet: Any, expected_type: Type):
    """
    Check if the given packet is of the expected type, otherwise raise a IOError.

    Parameters
    ----------
    packet
        The packet to check.
    expected_type
        The expected type.
    """
    if not isinstance(packet, expected_type):
        raise IOError(f"Invalid response '{type(packet)}' from remote dispatcher. This is a bug.")

@connector(schema='ssh')
class SshConnector(Connector):
    """A connector that provides remote access via SSH."""

    def __init__(self, url: Optional[str], host: HostType):
        super().__init__(url, host)

        self.ssh_opts: list[str] = getattr(host, 'ssh_opts') if hasattr(host, 'ssh_opts') else []
        if url is not None and url.startswith(f"{self.schema}://"):
            self.url = url
        else:
            self.url: str = f"{self.schema}://{getattr(host, 'ssh_host')}:{getattr(host, 'ssh_port')}"

        self.process: Optional[subprocess.Popen] = None
        self.conn: td.Connection
        self.is_open: bool = False

    def open(self):
        logger.connection_init(self)
        with open(td.__file__, 'rb') as f:
            tunnel_dispatcher_gz_b64 = base64.b64encode(zlib.compress(f.read(), 9)).decode('ascii')

        # Start the remote dispatcher by uploading it inline as base64
        param_debug = "--debug" if G.args.debug else ""
        command = self._ssh_command(f"env python3 -c \"$(echo '{tunnel_dispatcher_gz_b64}' | base64 -d | openssl zlib -d)\" {param_debug}")

        # pylint: disable=consider-using-with
        # The process must outlive this function.
        self.process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=sys.stderr)
        self.conn = td.Connection(self.process.stdout, self.process.stdin)

        try:
            response = self._request(td.PacketCheckAlive())
            _expect_response_packet(response, td.PacketAck)

            # As a last action record that the connection is opened successfully,
            # otherwise the finally block will kill the process.
            self.is_open = True
        except IOError as e:
            returncode = self.process.poll()
            if returncode is None:
                logger.connection_failed(str(e))
            else:
                logger.connection_failed(f"ssh exited with code {returncode}")
            raise
        finally:
            # If the connection failed for any reason, be sure to kill the background process.
            if not self.is_open:
                self.process.terminate()
                self.process = None

        logger.connection_established()

    def close(self):
        if self.is_open:
            self.conn.write_packet(td.PacketExit())

        if self.process is not None:
            if self.process.stdin is not None:
                self.process.stdin.close()
            self.process.wait()
            if self.process.stdout is not None:
                self.process.stdout.close()
            self.process = None

    def _request(self, packet: Any) -> Any:
        """Sends the request packet and returns the response.
        Propagates exceptions from raised from td.receive_packet."""
        self.conn.write_packet(packet)
        return td.receive_packet(self.conn, request=packet)

    def run(self,
            command: list[str],
            input: Optional[bytes] = None, # pylint: disable=redefined-builtin
            capture_output: bool = True,
            check: bool = True,
            user: Optional[str] = None,
            group: Optional[str] = None,
            umask: Optional[str] = None,
            cwd: Optional[str] = None) -> CompletedRemoteCommand:
        # Construct and send packet with process information
        request = td.PacketProcessRun(
            command=command,
            stdin=input,
            capture_output=capture_output,
            user=user,
            group=group,
            umask=umask,
            cwd=cwd)
        response = self._request(request)

        _expect_response_packet(response, td.PacketProcessCompleted)
        result = CompletedRemoteCommand(stdout=response.stdout,
                                        stderr=response.stderr,
                                        returncode=response.returncode)

        # Check output if requested
        if check and result.returncode != 0:
            raise subprocess.CalledProcessError(returncode=result.returncode,
                                                output=result.stdout,
                                                stderr=result.stderr,
                                                cmd=command)

        return result

    def stat(self, path: str, follow_links: bool = False, sha512sum: bool = False) -> Optional[StatResult]:
        # Construct and send packet with process information
        request = td.PacketStat(
            path=path,
            follow_links=follow_links,
            sha512sum=sha512sum)

        try:
            response = self._request(request)
        except ValueError:
            # File was not found, return None
            return None

        _expect_response_packet(response, td.PacketStatResult)
        return StatResult(
            type=response.type,
            mode=response.mode,
            owner=response.owner,
            group=response.group,
            size=response.size,
            mtime=response.mtime,
            ctime=response.ctime,
            sha512sum=response.sha512sum)

    def resolve_user(self, user: Optional[str]) -> str:
        request = td.PacketResolveUser(user=user)
        response = self._request(request)

        _expect_response_packet(response, td.PacketResolveResult)
        return response.value

    def resolve_group(self, group: Optional[str]) -> str:
        request = td.PacketResolveGroup(group=group)
        response = self._request(request)

        _expect_response_packet(response, td.PacketResolveResult)
        return response.value

    def upload(self,
            file: str,
            content: bytes,
            mode: Optional[str] = None,
            owner: Optional[str] = None,
            group: Optional[str] = None):
        request = td.PacketUpload(
                file=file,
                content=content,
                mode=mode,
                owner=owner,
                group=group)
        response = self._request(request)
        _expect_response_packet(response, td.PacketOk)

    def download(self, file: str) -> bytes:
        request = td.PacketDownload(file=file)
        response = self._request(request)

        _expect_response_packet(response, td.PacketDownloadResult)
        return response.content

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
