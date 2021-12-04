"""
Provides a class to manage a remote connection via the host's connector.
Stores state along with the connection.
"""

from __future__ import annotations

from types import TracebackType
from typing import Type, cast, Optional

import fora.script
from fora import globals as G, logger
from fora.connectors.connector import Connector, CompletedRemoteCommand, GroupEntry, StatResult, UserEntry
from fora.remote_settings import RemoteSettings
from fora.types import HostType

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
        self.base_settings: RemoteSettings = G.base_remote_settings

    def __enter__(self) -> Connection:
        self.connector.open()
        self.host.connection = self
        self._resolve_identity()
        return self

    def __exit__(self, exc_type: Optional[Type[BaseException]], exc: Optional[BaseException], traceback: Optional[TracebackType]) -> None:
        _ = (exc_type, exc, traceback)
        self.host.connection = cast(Connection, None)
        self.connector.close()

    def _resolve_identity(self) -> None:
        """
        Query the user and group under which we are operating, and store it
        in our base_settings. This ensures that the base settings reflect
        the actual user as which we operate.
        """
        user = self.resolve_user(None)
        group = self.resolve_group(None)
        self.base_settings.as_user = user
        self.base_settings.as_group = group
        self.base_settings.owner = user
        self.base_settings.group = group

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
        # pylint: disable=protected-access
        if fora.script._this is None:
            raise RuntimeError("Cannot resolve defaults, when no script is currently running.")

        # Overlay settings on top of defaults
        settings = fora.script.current_defaults().overlay(settings)

        # A function to check whether a mask is octal
        def check_mask(mask: Optional[str], name: str) -> None:
            if mask is None:
                raise ValueError(f"Error while resolving settings: {name} cannot be None!")
            try:
                int(mask, 8)
            except ValueError:
                raise ValueError(f"Error while resolving settings: {name} is '{mask}' but must be octal!") # pylint: disable=raise-missing-from

        settings.as_user  =  None if settings.as_user  is None else self.resolve_user(settings.as_user)
        settings.as_group =  None if settings.as_group is None else self.resolve_group(settings.as_group)
        settings.owner    =  None if settings.owner    is None else self.resolve_user(settings.owner)
        settings.group    =  None if settings.group    is None else self.resolve_group(settings.group)
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
        """See `fora.connectors.connector.Connector.run`."""
        logger.debug_args("Connection.run", locals())
        defaults = fora.script.current_defaults()
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
        """See `fora.connectors.connector.Connector.resolve_user`."""
        logger.debug_args("Connection.resolve_user", locals())
        return self.connector.resolve_user(user)

    def resolve_group(self, group: Optional[str]) -> Optional[str]:
        """See `fora.connectors.connector.Connector.resolve_group`."""
        logger.debug_args("Connection.resolve_group", locals())
        return self.connector.resolve_group(group)

    def stat(self, path: str, follow_links: bool = False, sha512sum: bool = False) -> Optional[StatResult]:
        """See `fora.connectors.connector.Connector.stat`."""
        logger.debug_args("Connection.stat", locals())
        return self.connector.stat(
            path=path,
            follow_links=follow_links,
            sha512sum=sha512sum)

    def upload(self,
            file: str,
            content: bytes,
            mode: Optional[str] = None,
            owner: Optional[str] = None,
            group: Optional[str] = None) -> None:
        """See `fora.connectors.connector.Connector.upload`."""
        logger.debug_args("Connection.upload", locals())
        return self.connector.upload(
            file=file,
            content=content,
            mode=mode,
            owner=owner,
            group=group)

    def download(self, file: str) -> bytes:
        """See `fora.connectors.connector.Connector.download`."""
        logger.debug_args("Connection.download", locals())
        return self.connector.download(file=file)

    def download_or(self, file: str, default: Optional[bytes] = None) -> Optional[bytes]:
        """
        Same as `Connection.download`, but returns the given default in case the file doesn't exist.

        Parameters
        ----------
        file
            The file to download.
        default
            The alternative to return if the file doesn't exist.

        Returns
        -------
        Optional[bytes]
            The downloaded file or the default if the file didn't exist.

        Raises
        ------
        fora.connectors.tunnel_dispatcher.RemoteOSError
            If the remote command fails for any reason other than file not found.
        IOError
            An error occurred with the connection.
        """
        try:
            return self.download(file=file)
        except ValueError:
            return default

    def query_user(self, user: str, default: Optional[UserEntry] = None) -> Optional[UserEntry]:
        """See `fora.connectors.connector.Connector.query_user`, but returns the given default in case the user doesn't exist."""
        try:
            return self.connector.query_user(user=user)
        except ValueError:
            return default

    def query_group(self, group: str, default: Optional[GroupEntry] = None) -> Optional[GroupEntry]:
        """See `fora.connectors.connector.Connector.query_group`, but returns the given default in case the group doesn't exist."""
        try:
            return self.connector.query_group(group=group)
        except ValueError:
            return default

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
