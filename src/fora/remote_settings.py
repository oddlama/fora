"""
Provides a class that represents execution defaults for a remote host.
"""

from __future__ import annotations
from typing import Any, Optional
from dataclasses import dataclass

@dataclass
class ResolvedRemoteSettings:
    """
    This class stores a resolved version of the RemoteSettings object,
    it only has more strict types for typechecking and is otherwise
    identical to the original object.
    """
    owner: str
    group: str
    file_mode: str
    dir_mode: str
    umask: str
    cwd: str
    as_user: Optional[str] = None
    as_group: Optional[str] = None

@dataclass
class RemoteSettings:
    """
    This class stores certain values that determine how things are executed on
    the remote host. This includes things such as the owner and group of newly
    created files, or the user as which commands are run.
    """
    as_user: Optional[str] = None
    as_group: Optional[str] = None
    owner: Optional[str] = None
    group: Optional[str] = None
    file_mode: Optional[str] = None
    dir_mode: Optional[str] = None
    umask: Optional[str] = None
    cwd: Optional[str] = None

    def overlay(self, settings: RemoteSettings) -> RemoteSettings:
        """
        Overlays settings on top of this. Values will only be overwritten
        if the new value is not None, effectively overlaying the given settings
        on top of the current settings.

        Parameters
        ----------
        settings
            The setting values to overwrite

        Returns
        -------
        The resulting overlayed remote settings
        """
        return RemoteSettings(
             as_user   = self.as_user   if settings.as_user   is None else settings.as_user,
             as_group  = self.as_group  if settings.as_group  is None else settings.as_group,
             owner     = self.owner     if settings.owner     is None else settings.owner,
             group     = self.group     if settings.group     is None else settings.group,
             file_mode = self.file_mode if settings.file_mode is None else settings.file_mode,
             dir_mode  = self.dir_mode  if settings.dir_mode  is None else settings.dir_mode,
             umask     = self.umask     if settings.umask     is None else settings.umask,
             cwd       = self.cwd       if settings.cwd       is None else settings.cwd)

    def __repr__(self) -> str:
        members = [None if self.as_user   is None else ("as_user", self.as_user),
                   None if self.as_group  is None else ("as_group", self.as_group),
                   None if self.owner     is None else ("owner", self.owner),
                   None if self.group     is None else ("group", self.group),
                   None if self.file_mode is None else ("file_mode", self.file_mode),
                   None if self.dir_mode  is None else ("dir_mode", self.dir_mode),
                   None if self.umask     is None else ("umask", self.umask),
                   None if self.cwd       is None else ("cwd", self.cwd)]
        existing_members: list[tuple[str, Any]] = [x for x in members if x is not None]
        member_str = ','.join([f"{n}={v}" for (n,v) in existing_members])
        return f"RemoteSettings{{{member_str}}}"
