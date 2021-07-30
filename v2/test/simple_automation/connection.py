"""
Provides an interface for remote connections.
"""

from simple_automation.connectors.connector import Connector

class Connection:
    """
    The connection class represents a connection to a host.
    It consists of a connector, which is actually responsible for
    providing remote access, and some internal state, which is used
    to determine what user code is run as by default, or related settings.
    """
    def __init__(self, host):
        self.host = host
        self.connector: Connector = self.host.connector(self.host)

        # TODO connection = connector + state
        self.umask = '0755'
        self.user = 'root'
        self.group = 'root'

    def __enter__(self):
        # Open the connection
        self.connector.open()
        self.host.connection = self
        return self

    def __exit__(self, type_t, value, traceback):
        self.host.connection = None
        self.connector.close()

    def run(self, command, checked=False, input=None, user=None, umask=None):
        pass
