"""
Defines the connector interface.
"""

class CompletedRemoteCommand:
    """
    The return value of run(), representing a finished remote process.
    """
    def __init__(self, stdout: str, stderr: str, returncode: int):
        self.stdout: str = stdout
        self.stderr: str = stderr
        self.returncode: int = returncode

class Connector:
    """
    The base class for all connectors.
    """

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

    def run(self, command, user, umask, checked=False, capture_output=False, input=None) -> CompletedRemoteCommand:
        """
        Runs the given command on the remote, returning a CompletedRemoteCommand
        containing the returned information (if any) and the status code.
        """
        raise NotImplementedError("Must be overwritten by subclass.")
