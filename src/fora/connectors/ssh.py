"""Contains a connector which handles connections to hosts via SSH."""

import base64
import zlib
from typing import Optional

import fora
from fora.connectors import tunnel_dispatcher as td
from fora.connectors.connector import connector
from fora.connectors.tunnel_connector import TunnelConnector
from fora.types import HostWrapper

@connector(schema='ssh')
class SshConnector(TunnelConnector):
    """A tunnel connector that provides remote access via SSH."""

    def __init__(self, url: Optional[str], host: HostWrapper):
        super().__init__(url, host)

        self.ssh_opts: list[str] = getattr(host, 'ssh_opts') if hasattr(host, 'ssh_opts') else []
        if url is not None and url.startswith(f"{self.schema}://"):
            self.url = url
        else:
            self.url: str = f"{self.schema}://{getattr(host, 'ssh_host')}:{getattr(host, 'ssh_port')}"

    def command(self) -> list[str]:
        """
        Constructs the full ssh command needed to execute a
        tunnel dispatcher on the remote host.

        Returns
        -------
        list[str]
            The required ssh command.
        """
        with open(td.__file__, 'rb') as f:
            tunnel_dispatcher_gz_b64 = base64.b64encode(zlib.compress(f.read(), 9)).decode('ascii')

        # Start the remote dispatcher by uploading it inline as base64
        param_debug = "--debug" if fora.args.debug else ""

        command = ["ssh"]
        command.extend(self.ssh_opts)
        command.append(self.url)
        command.append(f"env python3 -c \"$(echo '{tunnel_dispatcher_gz_b64}' | base64 -d | openssl zlib -d)\" {param_debug}")

        return command

    @classmethod
    def extract_hostname(cls, url: str) -> str:
        if not url.startswith(f"{cls.schema}:"):
            raise ValueError(f"Cannot extract hostname from url without matching schema (expected '{cls.schema}', got '{url}').")

        # strip ssh://
        # remaining: [user@]hostname[:port]
        hostname = url[len(cls.schema) + 3:]

        # Remove user
        pos = hostname.find("@")
        if pos >= 0:
            hostname = hostname[pos + 1:]

        # Remove port
        pos = hostname.find(":")
        if pos >= 0:
            hostname = hostname[:pos]

        return hostname
