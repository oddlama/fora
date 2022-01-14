"""Contains a connector which handles connections to hosts via SSH."""

import os
from typing import Optional

from fora import globals as G
from fora.connectors import tunnel_dispatcher as td
from fora.connectors.connector import connector
from fora.connectors.tunnel_connector import TunnelConnector
from fora.types import HostWrapper

@connector(schema='local')
class LocalConnector(TunnelConnector):
    """A tunnel connector that provides remote access to the current local machine via a subprocess."""

    def __init__(self, url: Optional[str], host: HostWrapper):
        super().__init__(url, host)

        if url is not None and url.startswith(f"{self.schema}:"):
            self.url = url
        else:
            self.url = "local:localhost"

    def command(self) -> list[str]:
        """
        Constructs the full command needed to execute a tunnel dispatcher on this machine.

        Returns
        -------
        list[str]
            The required ssh command.
        """
        command = ["python3", os.path.realpath(td.__file__)]
        if G.args.debug:
            command.append("--debug")
        return command

    @classmethod
    def extract_hostname(cls, url: str) -> str:
        if not url.startswith(f"{cls.schema}:"):
            raise ValueError(f"Cannot extract hostname from url without matching schema (expected '{cls.schema}', got '{url}').")
        hostname = url[len(cls.schema) + 1:]
        return hostname if len(hostname) > 0 else "localhost"
