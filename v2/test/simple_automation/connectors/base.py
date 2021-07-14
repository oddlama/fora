"""
Defines the connector interface.
"""

class CompletedRemoteCommand:
    """
    A wrapper for the information returned by a remote command.
    """
    def __init__(self, host):
        self.host = host
        self.stdout: str = None
        self.stderr: str = None
        self.return_code: int = None

class Connector:
    """
    The base class for all connectors.
    """

    def open(self):
        raise NotImplementedError("Must be implemented by subclasses!")

    def close(self):
        raise NotImplementedError("Must be implemented by subclasses!")

    def run(self, command, user, umask, checked=False, input=None):
        raise NotImplementedError("Must be implemented by subclasses!")
