"""
Provides a class to manage a remote connection via the host's connector.
Stores state along with the connection.
"""

from typing import Optional

import simple_automation
from simple_automation.connectors.connector import Connector, CompletedRemoteCommand
from simple_automation.remote_settings import RemoteSettings
from simple_automation.types import HostType, ScriptType, TaskType

class Connection:
    """
    The connection class represents a connection to a host.
    It consists of a connector, which is actually responsible for
    providing remote access, and some state, which determines defaults
    for the commands executed on the remote system.
    """

    base_settings = RemoteSettings(
        file_mode="600",
        dir_mode="700",
        umask="077",
        cwd="/tmp")
    """
    The base remote settings that are used, if no other preferences are given.
    """

    def __init__(self, host: HostType):
        self.host = host
        if self.host.connector is None:
            raise ValueError("host.connector must be set")
        self.connector: Connector = self.host.connector(host.url, host)

    def __enter__(self):
        # Open the connection
        self.connector.open()
        self.host.connection = self
        return self

    def __exit__(self, type_t, value, traceback):
        self.host.connection = None
        self.connector.close()

    def run(self,
            command: list[str],
            input: Optional[bytes] = None, # pylint: disable=redefined-builtin
            capture_output: bool = True,
            check: bool = False,
            user: Optional[str] = None,
            group: Optional[str] = None,
            umask: Optional[str] = None,
            cwd: Optional[str] = None) -> CompletedRemoteCommand:
        return self.connector.run(
            command=command,
            input=input,
            capture_output=capture_output,
            check=check,
            user=user,
            group=group,
            umask=umask,
            cwd=cwd)

    def verify_defaults(self, defaults: RemoteSettings):
        pass

    def resolve_defaults(self, settings: RemoteSettings) -> RemoteSettings:
        """
        Resolves (and verifies) the given settings against the current defaults,
        and returns tha actual values that should now be in effect. Verification
        means that this method will fail if e.g. the cwd doesn't exist on the remote.

        Parameters
        ----------
        settings
            Additional overrides for the current defaults

        Returns
        -------
        RemoteSettings
            The resolved settings
        """
        if not (isinstance(simple_automation.this, ScriptType) or isinstance(simple_automation.this, TaskType)):
            raise RuntimeError("Cannot resolve defaults, when neither a script nor a task is currently running.")

        # Overlay settings on top of defaults and base defaults
        settings = simple_automation.this.current_defaults().overlay(settings)
        settings = Connection.base_settings.overlay(settings)

        # A function to check whether a mask is octal
        def check_mask(mask: Optional[str], name: str):
            if mask is None:
                raise ValueError(f"Error while resolving settings: {name} cannot be None!")
            try:
                int(mask, 8)
            except ValueError:
                raise ValueError(f"Error while resolving settings: {name} is '{mask}' but must be octal!")

        settings.as_user = self.resolve_user(settings.as_user)
        settings.as_group = self.resolve_group(settings.as_group)
        settings.owner = self.resolve_user(settings.owner)
        settings.group = self.resolve_group(settings.group)
        check_mask(settings.file_mode, "file_mode")
        check_mask(settings.dir_mode, "dir_mode")
        check_mask(settings.umask, "umask")
        settings.cwd = self.resolve_dir(settings.cwd)

        return settings

    def resolve_user(self, user: str) -> str:
        return ""

    def resolve_group(self, group: str) -> str:
        return ""

    def resolve_dir(self, path: str) -> str:
        return ""

    def stat(self, path: str):
        # TODO
        pass

def open_connection(host: HostType) -> Connection:
    """
    Returns a connection (context manager) that opens the connection when it is entered and
    closes it when it is exited. The connection can be obtained via host.connection,
    as long as it is opened.

    Parameters
    ----------
    host
        The host to which a connection should be opened

    Returns
    -------
    Connection
        The connection (context manager)
    """
    return Connection(host)
