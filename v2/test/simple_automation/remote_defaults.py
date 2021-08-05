"""
Provides a class that represents execution defaults for a remote host.
"""

from typing import Optional

class RemoteDefaults:
    """
    This class stores the default values for certain execution settings
    for a remote host. This includes things such as the user, group or
    similar variables that determine how things are executed.
    """
    def __init__(self,
                 as_user: Optional[str] = None,
                 as_group: Optional[str] = None,
                 owner: Optional[str] = None,
                 group: Optional[str] = None,
                 file_mode: Optional[str] = None,
                 dir_mode: Optional[str] = None,
                 umask: Optional[str] = None,
                 cwd: Optional[str] = None):
        self.as_user   = as_user
        self.as_group  = as_group
        self.owner     = owner
        self.group     = group
        self.file_mode = file_mode
        self.dir_mode  = dir_mode
        self.umask     = umask
        self.cwd       = cwd

    def overlay(self, other_defaults: RemoteDefaults):
        """
        Replaces values that are None with the values from the other
        defaults, effectively overlaying these defaults on top of the others.

        Parameters
        ----------
        other_defaults
            The other default values to overlay
        """
        if self.as_user is None:
            self.as_user = other_defaults.as_user
        if self.as_group is None:
            self.as_group = other_defaults.as_group
        if self.owner is None:
            self.owner = other_defaults.owner
        if self.group is None:
            self.group = other_defaults.group
        if self.file_mode is None:
            self.file_mode = other_defaults.file_mode
        if self.dir_mode is None:
            self.dir_mode = other_defaults.dir_mode
        if self.umask is None:
            self.umask = other_defaults.umask
        if self.cwd is None:
            self.cwd = other_defaults.cwd
