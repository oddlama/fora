import inspect
import os
import sys

import simple_automation.loader

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
    print("Script stack (most recent call last):")
    def print_frame(f):
        print(f"  File \"{f.filename}\", line {f.lineno}, in {f.frame.f_code.co_name}", file=sys.stderr)
        for context in f.code_context:
            print(f"    {context.strip()}", file=sys.stderr)

    for _, frame in simple_automation.loader.script_stack:
        print_frame(frame)
    if currentframe is not None:
        print_frame(currentframe)

def script(name, script, recursive=False):
    outer_frame = inspect.getouterframes(inspect.currentframe())[1]
    if not recursive:
        for meta, _ in simple_automation.loader.script_stack:
            if os.path.samefile(script, meta.loaded_from):
                _print_script_trace(outer_frame)
                raise RuntimeError(f"Invalid recursive call to script '{script}'. Use recursive=True to allow this.")
    # TODO
