"""
Defines the connector interface.
"""

from __future__ import annotations

from simple_automation.types import HostType
from typing import Callable, Optional

class CompletedRemoteCommand:
    """
    The return value of run(), representing a finished remote process.
    """
    def __init__(self, stdout: Optional[bytes], stderr: Optional[bytes], returncode: int):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode

class Connector:
    """
    The base class for all connectors.
    """

    schema: str
    """
    The schema of the connector. Must match the schema used in urls of this connector,
    such as `ssh` for `ssh://...`. May also be shown in messages like:

        "Establishing connecting to {host} via {schema}"

    Overwrite this in your connector subclass. Must be unique among all connectors.
    """

    registered_connectors: dict[str, Callable[[str, HostType], Connector]] = {}
    """
    The list of all registered connectors.
    """

    def __init__(self, url: Optional[str], host: HostType):
        self.url = url
        self.host = host

    def open(self) -> None:
        """
        Opens the connection to the remote host.
        """
        raise NotImplementedError("Must be overwritten by subclass.")

    def close(self) -> None:
        """
        Closes the connection to the remote host.
        """
        raise NotImplementedError("Must be overwritten by subclass.")

    def run(self, command: list[str],
            input: bytes,
            capture_output: bool,
            check: bool,
            user: Optional[str],
            group: Optional[str],
            umask: Optional[str],
            cwd: Optional[str]) -> CompletedRemoteCommand:
        """
        Runs the given command on the remote, returning a CompletedRemoteCommand
        containing the returned information (if any) and the status code.
        """
        raise NotImplementedError("Must be overwritten by subclass.")

def connector(cls):
    if not hasattr(cls, 'schema'):
        raise RuntimeError(f"{cls.__name__} was decorated with @connector but is not exposing a '{cls.__name__}.schema' attribute.")
    Connector.registered_connectors[cls.schema] = cls
    return cls
