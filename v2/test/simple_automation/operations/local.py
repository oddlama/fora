import inspect
import os
import sys

import simple_automation

def task(name):
    pass

def _error_recursive_script_loop(script):
    print(f"Detected recursive call to script {script}. Use recursive=True to allow this.")
    print("Script stack:")
    # TODO we can actually find out the exact invocation line using a stacktrace.
    for meta in simple_automation.script_stack:
        # TODO proper color switch and logic
        if os.path.samefile(script, meta.loaded_from):
            print(f"  [1;31m→ {meta.loaded_from}[m ({meta.name})")
        else:
            print(f"    {meta.loaded_from} ({meta.name})")
    print(f"  → {script} (this call)")
    print(inspect.getouterframes(inspect.currentframe())[2])

    try:
        raise RuntimeError(f"Invalid recursive call to script {script}")
    except RuntimeError:
        ei = sys.exc_info()
        raise ei[1].with_traceback(None)

def script(name, script, recursive=False):
    if not recursive:
        for meta in simple_automation.script_stack:
            if os.path.samefile(script, meta.loaded_from):
                # TODO how to signal error properly
                # we need to close connections, we need proper output
                # we dont want a simple die.
                # maybe allow REPL to be started?
                _error_recursive_script_loop(script)
                return
    # TODO
