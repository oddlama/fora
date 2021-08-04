"""
Provides a class to manage a remote connection via the host's connector.
Stores state along with the connection.
"""

from typing import Optional
from simple_automation.connectors.connector import Connector, CompletedRemoteCommand

class Connection:
    """
    The connection class represents a connection to a host.
    It consists of a connector, which is actually responsible for
    providing remote access, and some internal state, which is used
    to determine what user code is run as by default, or related settings.
    """
    def __init__(self, host):
        self.host = host
        self.connector: Connector = self.host.connector(host.url, host)

        # TODO connection = connector + state
        self.umask: str = '0755'
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
