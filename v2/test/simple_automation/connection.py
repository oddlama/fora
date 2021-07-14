"""
Provides the 
"""

from connectors.base import Connector

class Connection:
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
