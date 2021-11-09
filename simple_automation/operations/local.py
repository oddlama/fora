"""
Provides operations that are related to the local system on which the
simple_automation scripts are executed.
"""

import inspect
import os

from simple_automation.loader import script_stack, run_script
from simple_automation.utils import AbortExecutionSignal

# TODO check= or ignore_errors=
def script(name: str,
           script: str, # pylint: disable=redefined-outer-name
           recursive: bool = False):
    # Asserts that the call is not recursive, if not explicitly allowed
    if not recursive:
        for meta, _ in script_stack:
            if os.path.samefile(script, meta.loaded_from):
                raise AbortExecutionSignal(f"Invalid recursive call to script '{script}'. Use recursive=True to allow this.")

    outer_frame = inspect.getouterframes(inspect.currentframe())[1]
    run_script(script, outer_frame, name=name)
