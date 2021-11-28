"""Contains a connector which handles connections to hosts via SSH."""

import base64
import zlib
from typing import Optional

from fora import globals as G
from fora.connectors import tunnel_dispatcher as td
from fora.connectors.connector import connector
from fora.connectors.tunnel_connector import TunnelConnector
from fora.types import HostType

@connector(schema='ssh')
class SshConnector(TunnelConnector):
    """A tunnel connector that provides remote access via SSH."""

    def __init__(self, url: Optional[str], host: HostType):
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
        param_debug = "--debug" if G.args.debug else ""

        command = ["ssh"]
        command.extend(self.ssh_opts)
        command.append(self.url)
        command.append(f"env python3 -c \"$(echo '{tunnel_dispatcher_gz_b64}' | base64 -d | openssl zlib -d)\" {param_debug}")

        return command
