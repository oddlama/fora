"""
Provides operations that are related to the local system on which the
simple_automation scripts are executed.
"""

import inspect
import os

from simple_automation import logger
from simple_automation.loader import script_trace, script_stack, run_script
from simple_automation.utils import AbortExecutionSignal

def task(name: str):
    pass

# TODO checked or check or ignore_errors
def script(name: str, script: str, recursive: bool = False):
    # Asserts that the call is not recursive, if not explicitly allowed
    if not recursive:
        outer_frame = inspect.getouterframes(inspect.currentframe())[1]
        for meta, _ in script_stack:
            if os.path.samefile(script, meta.loaded_from):
                print(script_trace(currentframe=outer_frame))
                print(f"Invalid recursive call to script '{script}'. Use recursive=True to allow this.")
                raise AbortExecutionSignal()

    logger.run_script(name, script)
    run_script(script, outer_frame)
