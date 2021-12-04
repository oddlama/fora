"""Contains a connector base which handles communication via any spawned subprocess command that can run a tunnel dispatcher on the remote host."""

import sys
import subprocess
from typing import Any, Optional, Type, cast

from fora import logger
from fora.connectors import tunnel_dispatcher as td
from fora.connectors.connector import CompletedRemoteCommand, Connector, GroupEntry, StatResult, UserEntry
from fora.types import HostType

def _expect_response_packet(packet: Any, expected_type: Type) -> None:
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

class TunnelConnector(Connector):
    """A connector that handles requests via an externally supplied subprocess running a tunnel dispatcher.
    Any subclass must override command()."""

    def __init__(self, url: Optional[str], host: HostType):
        super().__init__(url, host)

        self.process: Optional[subprocess.Popen] = None
        self.conn: td.Connection
        self.is_open: bool = False

    def command(self) -> list[str]:
        """Returns the command that should be executed to open a tunnel dispatcher to the destination."""
        raise NotImplementedError("Must be overwritten by subclass.")

    def open(self) -> None:
        logger.connection_init(self)

        # pylint: disable=consider-using-with
        # The process must outlive this function.
        self.process = subprocess.Popen(self.command(), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=sys.stderr)
        if self.process.stdout is None or self.process.stdin is None:
            raise RuntimeError("Subprocess has no stdin/stdout. If is a bug.")
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

    def close(self) -> None:
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

        if isinstance(response, td.PacketProcessError):
            raise ValueError(response.message)

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
        return cast(td.PacketResolveResult, response).value

    def resolve_group(self, group: Optional[str]) -> str:
        request = td.PacketResolveGroup(group=group)
        response = self._request(request)

        _expect_response_packet(response, td.PacketResolveResult)
        return cast(td.PacketResolveResult, response).value

    def query_user(self, user: str) -> UserEntry:
        request = td.PacketQueryUser(user=user)
        response = self._request(request)

        _expect_response_packet(response, td.PacketUserEntry)
        return UserEntry(
            name=response.name,
            uid=response.uid,
            group=response.group,
            gid=response.gid,
            groups=response.groups,
            password_hash=response.password_hash,
            gecos=response.gecos,
            home=response.home,
            shell=response.shell)

    def query_group(self, group: str) -> GroupEntry:
        request = td.PacketQueryGroup(group=group)
        response = self._request(request)

        _expect_response_packet(response, td.PacketGroupEntry)
        return GroupEntry(
            name=response.name,
            gid=response.gid,
            members=response.members)

    def upload(self,
            file: str,
            content: bytes,
            mode: Optional[str] = None,
            owner: Optional[str] = None,
            group: Optional[str] = None) -> None:
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
        return cast(td.PacketDownloadResult, response).content
