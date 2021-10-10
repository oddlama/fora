import inspect
import os
import sys

from simple_automation.loader import script_stack, run_script
from simple_automation import logger

def task(name):
    pass

def _print_script_trace(currentframe=None):
    """
    Prints a script trace similar to a python backtrace.

    Parameters
    ----------
    currentframe
        An additional FrameInfo object for a future script invocation,
        which isn't yet part of the stack.
    """
    print("Script stack (most recent call last):", file=sys.stderr)
    def print_frame(f):
        print(f"  File \"{f.filename}\", line {f.lineno}, in {f.frame.f_code.co_name}", file=sys.stderr)
        for context in f.code_context:
            print(f"    {context.strip()}", file=sys.stderr)

    for _, frame in script_stack:
        print_frame(frame)
    if currentframe is not None:
        print_frame(currentframe)

def script(name, script, recursive=False):
    # Check if the invocation is recursive
    if not recursive:
        outer_frame = inspect.getouterframes(inspect.currentframe())[1]
        for meta, _ in script_stack:
            if os.path.samefile(script, meta.loaded_from):
                _print_script_trace(outer_frame)
                raise RuntimeError(f"Invalid recursive call to script '{script}'. Use recursive=True to allow this.")

    logger.run_script(name, script)
    run_script(script, outer_frame)
