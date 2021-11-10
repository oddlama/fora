""" Provides operations that are related to the local system on which the
simple_automation scripts are executed.
"""

import inspect
import os
from typing import Any, Optional

from simple_automation.loader import script_stack, run_script

def script(script: str, # pylint: disable=redefined-outer-name
           recursive: bool = False,
           params: dict[str, Any] = None,
           name: Optional[str] = None):
    """
    Executes the given script for the current host.
    Useful to split functionality into smaller sub-scripts.

    Scripts can take parameters. Parameters to scripts are passed by
    supplying a `params` dictionary. The script declares its parameters
    by annotating them. (The annotation then transparently extracts the
    value from a separately passed global variable).

        from simple_automation.script import params

        @params
        class params:
            username: str
            website_title: str = "Default website title."

        # Use a parameter
        print(params.username)

    Parameters
    ----------
    script
        The local path to the script to execute.
    recursive
        Whether recursive calls should be allowed.
    params
        The parameters for the script.
    name
        The name for the script execution (used for logging).
    """
    # Asserts that the call is not recursive, if not explicitly allowed
    if not recursive:
        for meta, _ in script_stack:
            if os.path.samefile(script, meta.loaded_from):
                raise ValueError(f"Invalid recursive call to script '{script}'. Use recursive=True to allow this.")

    outer_frame = inspect.getouterframes(inspect.currentframe())[1]
    run_script(script, outer_frame, params=params, name=name)
