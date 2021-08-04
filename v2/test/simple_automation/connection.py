"""
Provides a class to manage a remote connection via the host's connector.
Stores state along with the connection.
"""

from typing import Optional

from simple_automation.connectors.connector import Connector, CompletedRemoteCommand
from simple_automation.types import HostType

class Connection:
    """
    The connection class represents a connection to a host.
    It consists of a connector, which is actually responsible for
    providing remote access, and some state, which determines defaults
    for the commands executed on the remote system.
    """
    def __init__(self, host: HostType):
        self.host = host
        if self.host.connector is None:
            raise ValueError("host.connector must be set")
        self.connector: Connector = self.host.connector(host.url, host)

        self.umask: str = '077'
        self.user: str = 'root'
        self.group: str = 'root'

    def __enter__(self):
        # Open the connection
        self.connector.open()
        self.host.connection = self
        return self

    def __exit__(self, type_t, value, traceback):
        self.host.connection = None
        self.connector.close()

    def run(self, command: list[str],
            input: Optional[bytes] = None, # pylint: disable=redefined-builtin
            capture_output: bool = True,
            check: bool = False,
            user: Optional[str] = None,
            group: Optional[str] = None,
            umask: Optional[str] = None,
            cwd: Optional[str] = None) -> CompletedRemoteCommand:
        pass
