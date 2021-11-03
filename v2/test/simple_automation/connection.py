"""
Provides a class to manage a remote connection via the host's connector.
Stores state along with the connection.
"""

from typing import cast, Optional

import simple_automation
from simple_automation.connectors.connector import Connector, CompletedRemoteCommand, StatResult
from simple_automation.remote_settings import RemoteSettings
from simple_automation.types import HostType, ScriptType

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

    def __enter__(self):
        # Open the connection
        self.connector.open()
        self.host.connection = self
        return self

    def __exit__(self, type_t, value, traceback):
        self.host.connection = None
        self.connector.close()

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
        if not isinstance(simple_automation.this, ScriptType):
            raise RuntimeError("Cannot resolve defaults, when no script is currently running.")

        # Overlay settings on top of defaults
        settings = simple_automation.this.current_defaults().overlay(settings)

        # A function to check whether a mask is octal
        def check_mask(mask: Optional[str], name: str):
            if mask is None:
                raise ValueError(f"Error while resolving settings: {name} cannot be None!")
            try:
                int(mask, 8)
            except ValueError:
                raise ValueError(f"Error while resolving settings: {name} is '{mask}' but must be octal!") # pylint: disable=raise-missing-from

        settings.as_user = self.resolve_user(settings.as_user)
        settings.as_group = self.resolve_group(settings.as_group)
        settings.owner = self.resolve_user(settings.owner)
        settings.group = self.resolve_group(settings.group)
        check_mask(settings.file_mode, "file_mode")
        check_mask(settings.dir_mode, "dir_mode")
        check_mask(settings.umask, "umask")
        if settings.cwd:
            s = self.stat(settings.cwd)
            if not s:
                raise ValueError(f"The selected working directory '{settings.cwd}' doesn't exist!")
            if s.type != "dir":
                raise ValueError(f"The selected working directory '{settings.cwd}' is not a directory!")

        return settings

    def run(self,
            command: list[str],
            input: Optional[bytes] = None, # pylint: disable=redefined-builtin
            capture_output: bool = True,
            check: bool = True,
            user: Optional[str] = None,
            group: Optional[str] = None,
            umask: Optional[str] = None,
            cwd: Optional[str] = None) -> CompletedRemoteCommand:
        """
        See :func:`simple_automation.connectors.connector.run`.
        """
        defaults = cast(ScriptType, simple_automation.this).current_defaults()
        return self.connector.run(
            command=command,
            input=input,
            capture_output=capture_output,
            check=check,
            user=user if user is not None else defaults.as_user,
            group=group if group is not None else defaults.as_group,
            umask=umask if umask is not None else defaults.umask,
            cwd=cwd if cwd is not None else defaults.cwd)

    def resolve_user(self, user: Optional[str]) -> Optional[str]:
        """
        See :func:`simple_automation.connectors.connector.resolve_user`.
        """
        return self.connector.resolve_user(user)

    def resolve_group(self, group: Optional[str]) -> Optional[str]:
        """
        See :func:`simple_automation.connectors.connector.resolve_group`.
        """
        return self.connector.resolve_group(group)

    def stat(self, path: str, follow_links: bool = False, sha512sum: bool = False) -> Optional[StatResult]:
        """
        See :func:`simple_automation.connectors.connector.stat`.
        """
        return self.connector.stat(
            path=path,
            follow_links=follow_links,
            sha512sum=sha512sum)

    def upload(self,
            file: str,
            content: bytes,
            mode: Optional[str] = None,
            owner: Optional[str] = None,
            group: Optional[str] = None):
        """
        See :func:`simple_automation.connectors.connector.upload`.
        """
        return self.connector.upload(
            file=file,
            content=content,
            mode=mode,
            owner=owner,
            group=group)

    def download(self, file: str) -> bytes:
        """
        See :func:`simple_automation.connectors.connector.download`.
        """
        return self.connector.download(file=file)

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
