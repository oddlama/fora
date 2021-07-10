"""
This module provides all script related functionality, as well as a global
variable 'this' that may be used inside a script module to interact with the
execution framework.
"""

from typing import Optional

from .types import HostType

class ScriptMeta:
    """
    This class represents all meta information available to a script module when itself is being loaded.
    It allows a module to access and modify its associated meta-information.
    """

    def __init__(self, name: str, loaded_from: str):
        self.name: str = name
        """
        The name of the group. Must not be changed.
        """

        self.loaded_from: str = loaded_from
        """
        The original file path of the instanciated module.
        """

this: Optional[ScriptMeta] = None
"""
This variable holds all meta information available to a script module when itself is being run.
This variable should only ever be used in the context of a script module as shown below, otherwise
it will be None.

It allows the module to interact with the simple_automation framework while it is being executed
to set status messages or retrieve other meta information.

When writing a script module, you can simply import :attr:`simple_automation.script.this`,
which exposes an API to access/modify this information.

.. topic:: Example: Using meta information (deploy.py)

    .. code-block:: python

        from simple_automation.script import this, host

        print(f"Running {__name__} on {host.meta.name}")
        this.status("Some status message")
"""
