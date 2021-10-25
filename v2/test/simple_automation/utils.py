"""
Provides utility functions.
"""

import inspect
import os
import sys
import traceback
import uuid
from types import ModuleType
from typing import TypeVar, Callable, Iterable, Callable, Optional

import importlib.machinery
import importlib.util

from simple_automation.types import ScriptType

T = TypeVar('T')

# A set of all modules names that are dynamically loaded modules.
# These are guaranteed to be unique across all possible modules,
# as a random uuid will be generated at load-time for each module.
dynamically_loaded_modules: set[str] = set()

class AbortExecutionSignal(Exception):
    """
    An exception used to indicate an error condition that requires the execution to
    be stopped for the current host. The exception stack will not be printed and should
    be logged before raising this exception.
    """

def print_warning(msg: str):
    """
    Prints a message with a colored 'warning: ' prefix.
    """
    print(f"[1;33mwarning:[m {msg}")

def print_error(msg: str, loc=None):
    """
    Prints a message with a colored 'error: ' prefix.
    """
    if loc is None:
        print(f"[1;31merror:[m {msg}")
    else:
        print(f"[1m{loc}: [1;31merror:[m {msg}")

def die_error(msg: str, loc=None, status_code=1):
    """
    Prints a message with a colored 'error: ' prefix, and exit with the given status code afterwards.
    """
    print_error(msg, loc=loc)
    sys.exit(status_code)

class CycleError(ValueError):
    """
    An error that is throw to report a cycle in a graph that must be cycle free.
    """

    def __init__(self, msg, cycle):
        """
        This error is thrown when a cycle is detected in a graph, and
        the throwing function can't deal with cyclic graphs.
        """
        super().__init__(msg)
        self.cycle = cycle

def load_py_module(file: str, pre_exec: Optional[Callable[[ModuleType], None]] = None) -> ModuleType:
    """
    Loads a module from the given filename and assigns a unique module name to it.
    Calling this function twice for the same file will yield distinct instances.
    """
    module_id = str(uuid.uuid4()).replace('-', '_')
    module_name = f"{os.path.splitext(os.path.basename(file))[0]}__dynamic__{module_id}"
    dynamically_loaded_modules.add(module_name)
    loader = importlib.machinery.SourceFileLoader(module_name, file)
    spec = importlib.util.spec_from_loader(loader.name, loader)
    if spec is None:
        raise ValueError(f"Failed to load module from file '{file}'")

    mod = importlib.util.module_from_spec(spec)
    # Run pre_exec callback after the module is loaded but before it is executed
    if pre_exec is not None:
        pre_exec(mod)
    loader.exec_module(mod)
    return mod

def rank_sort(vertices: Iterable[T], preds_of: Callable[[T], Iterable[T]], childs_of: Callable[[T], Iterable[T]]) -> dict[T, int]:
    """
    Calculates the top-down rank for each vertex. Supports graphs with multiple components.
    The graph must not have any cycles. If it does, a CycleError might be thrown, but this
    is not guaranteed and can also result in the resulting rank containing back-edges.
    By checking if the rank assignment contains a back-edge, a cycle in the graph can be detected
    retroactively.

    Parameters
    ----------
    vertices : Iterable[T]
        A list of vertices
    preds_of : Callable[[T], Iterable[T]]
        A function that returns a list of predecessors given a vertex
    childs_of : Callable[[T], Iterable[T]]
        A function that returns a list of successors given a vertex

    Returns
    -------
    dict[T, int]
        A dict associating a rank to each vertex
    """
    # Create a mapping of vertices to ranks.
    ranks = {v: -1 for v in vertices}

    # While there is at least one node without a rank,
    # find the "tree root" of that portion of the graph and
    # assign ranks to all reachable children without ranks.
    while -1 in ranks.values():
        # Start at any unvisited node
        root = next(filter(lambda k: ranks[k] == -1, ranks.keys()))

        # Initialize a visited mapping to detect cycles
        visited = {v: False for v in vertices}
        visited[root] = True

        # Find the root of the current subtree,
        # or detect a cycle and abort.
        while any(True for _ in preds_of(root)):
            root = next(x for x in preds_of(root))
            if visited[root]:
                cycle = list(filter(lambda v: visited[v], vertices))
                raise CycleError("Cannot apply rank_sort to cyclic graph.", cycle)

            visited[root] = True

        # The root node has rank 0
        ranks[root] = 0

        # Now assign increasing ranks to children in a breadth-first manner
        # to avoid transitive dependencies from causing additional subtree-updates.
        # We start with a list of nodes to process and their parents stored as pairs.
        needs_rank_list = list((c, root) for c in childs_of(root))
        while len(needs_rank_list) > 0:
            # Take the next node to process
            n, p = needs_rank_list.pop(0)
            r = ranks[p] + 1

            # Skip nodes that already have a rank
            # higher than the one we would assign
            if ranks[n] >= r:
                continue

            # Assign rank
            ranks[n] = r
            # Queue childen for rank assignment
            needs_rank_list.extend([(c, n) for c in childs_of(n)])

    return ranks

def script_trace(script_stack: list[tuple[ScriptType, inspect.FrameInfo]],
                 include_root: bool = False):
    """
    Creates a script trace similar to a python backtrace.

    Parameters
    ----------
    script_stack
        The script stack to print
    include_root
        Whether or not to include the root frame in the script trace.
    """
    def format_frame(f):
        frame = f"  File \"{f.filename}\", line {f.lineno}, in {f.frame.f_code.co_name}\n"
        for context in f.code_context:
            frame += f"    {context.strip()}\n"
        return frame

    ret = "Script stack (most recent call last):\n"
    for _, frame in script_stack if include_root else script_stack[1:]:
        ret += format_frame(frame)

    return ret[:-1] # Strip last newline

def print_exception(exc_type, exc_info, tb):
    """
    A function that hook that prints an exception traceback beginning from the
    last dynamically loaded module, but including a script stack so the error
    location is more easily understood and printed in a cleaner way.
    """

    original_tb = tb
    last_dynamic_tb = None
    # Iterate over all frames in the traceback and
    # find the last dynamically loaded module in the traceback
    while tb:
        frame = tb.tb_frame
        if "__name__" in frame.f_locals and frame.f_locals['__name__'] in dynamically_loaded_modules:
            last_dynamic_tb = tb
        tb = tb.tb_next

    # Print the script stack if at least one user script is involved,
    # which means we need to have at least two entries as the root context
    # is also involved.
    script_stack = getattr(exc_info, 'script_stack', None)
    if script_stack is not None and len(script_stack) > 1:
        print(script_trace(script_stack), file=sys.stderr)

    # Print the exception as usual begining from the last dynamic module,
    # if one is involved.
    traceback.print_exception(exc_type, exc_info, last_dynamic_tb or original_tb)

def install_exception_hook():
    """
    Installs a new global exception handler, that will modify the
    traceback of exceptions raised from dynamically loaded modules
    so that they are printed in a cleaner and more meaningful way (for the user).
    """

    sys.excepthook = print_exception
