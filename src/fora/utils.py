"""
Provides utility functions.
"""

from __future__ import annotations

import importlib
import importlib.machinery
import importlib.util
import inspect
import os
import pkgutil
import sys
import traceback
import uuid
from types import ModuleType, TracebackType
from typing import Any, NoReturn, Type, TypeVar, Callable, Iterable, Optional, Union

import fora.group
import fora.host
import fora.script

from fora.types import GroupType, HostType, ScriptType
from fora.logger import col

T = TypeVar('T')

# A set of all modules names that are dynamically loaded modules.
# These are guaranteed to be unique across all possible modules,
# as a random uuid will be generated at load-time for each module.
dynamically_loaded_modules: set[str] = set()

class CycleError(ValueError):
    """An error that is throw to report a cycle in a graph that must be cycle free."""

    def __init__(self, msg: str, cycle: list[Any]):
        super().__init__(msg)
        self.cycle = cycle

class SetVariableContextManager:
    """A context manager that sets a variable on enter and resets it to the previous value on exit."""
    def __init__(self, obj: object, var: str, value: Any):
        self.obj: object = obj
        self.var: str = var
        self.value: Any = value
        self.old_value: Any = getattr(self.obj, self.var)

    def __enter__(self) -> SetVariableContextManager:
        setattr(self.obj, self.var, self.value)
        return self

    def __exit__(self, exc_type: Optional[Type[BaseException]], exc: Optional[BaseException], tb: Optional[TracebackType]) -> None:
        _ = (exc_type, exc, tb)
        setattr(self.obj, self.var, self.old_value)

    def update(self, value: Any) -> None:
        """Updates the stored variable while the context manager is active."""
        self.value = value
        setattr(self.obj, self.var, self.value)

def print_warning(msg: str) -> None:
    """Prints a message with a (possibly colored) 'warning: ' prefix."""
    print(f"{col('[1;33m')}warning:{col('[m')} {msg}")

def print_error(msg: str, loc: Optional[str] = None) -> None:
    """Prints a message with a (possibly colored) 'error: ' prefix."""
    if loc is None:
        print(f"{col('[1;31m')}error:{col('[m')} {msg}", file=sys.stderr)
    else:
        print(f"{col('[1m')}{loc}: {col('[1;31m')}error:{col('[m')} {msg}", file=sys.stderr)

def die_error(msg: str, loc: Optional[str] = None, status_code: int = 1) -> NoReturn:
    """Prints a message with a colored 'error: ' prefix, and exit with the given status code afterwards."""
    print_error(msg, loc=loc)
    sys.exit(status_code)

def set_this_group(value: GroupType) -> SetVariableContextManager:
    """A context manager to temporarily set `fora.group._this` to the given value."""
    return SetVariableContextManager(fora.group, '_this', value)

def set_this_host(value: HostType) -> SetVariableContextManager:
    """A context manager to temporarily set `fora.host._this` to the given value."""
    return SetVariableContextManager(fora.host, '_this', value)

def set_this_script(value: ScriptType) -> SetVariableContextManager:
    """A context manager to temporarily set `fora.script._this` to the given value."""
    return SetVariableContextManager(fora.script, '_this', value)

def set_current_host(host: HostType) -> SetVariableContextManager:
    """A context manager to temporarily set `fora.host.current_host` to the given value."""
    return SetVariableContextManager(fora.host, 'current_host', host)

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
    vertices
        A list of vertices
    preds_of
        A function that returns a list of predecessors given a vertex
    childs_of
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

            # If the rank to assign is greater than the total number of nodes, the graph must be cyclic.
            if r > len(list(vertices)):
                raise CycleError("Cannot apply rank_sort to cyclic graph.", [p])

            # Skip nodes that already have a rank higher than
            # or equal to the one we would assign
            if ranks[n] >= r:
                continue

            # Assign rank
            ranks[n] = r
            # Queue childenii for rank assignment
            needs_rank_list.extend([(c, n) for c in childs_of(n)])

    return ranks

def script_trace(script_stack: list[tuple[ScriptType, inspect.FrameInfo]],
                 include_root: bool = False) -> str:
    """
    Creates a script trace similar to a python backtrace.

    Parameters
    ----------
    script_stack
        The script stack to print
    include_root
        Whether or not to include the root frame in the script trace.
    """
    def format_frame(f: inspect.FrameInfo) -> str:
        frame = f"  File \"{f.filename}\", line {f.lineno}, in {f.frame.f_code.co_name}\n"
        if f.code_context is not None:
            for context in f.code_context:
                frame += f"    {context.strip()}\n"
        return frame

    ret = "Script stack (most recent call last):\n"
    for _, frame in script_stack if include_root else script_stack[1:]:
        ret += format_frame(frame)

    return ret[:-1] # Strip last newline

def print_exception(exc_type: Optional[Type[BaseException]], exc_info: Optional[BaseException], tb: Optional[TracebackType]) -> None:
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

def install_exception_hook() -> None:
    """
    Installs a new global exception handler, that will modify the
    traceback of exceptions raised from dynamically loaded modules
    so that they are printed in a cleaner and more meaningful way (for the user).
    """
    sys.excepthook = print_exception

def import_submodules(package: Union[str, ModuleType], recursive: bool = False) -> dict[str, ModuleType]:
    """
    Import all submodules of a module, possibly recursively including subpackages.

    Parameters
    ----------
    package
        The package to import all submodules from.
    recursive
        Whether to recursively include subpackages.

    Returns
    -------
    dict[str, ModuleType]
    """
    if isinstance(package, str):
        package = importlib.import_module(package)
    results = {}
    for _, name, is_pkg in pkgutil.walk_packages(package.__path__): # type: ignore[attr-defined]
        full_name = package.__name__ + '.' + name
        results[full_name] = importlib.import_module(full_name)
        if recursive and is_pkg:
            results.update(import_submodules(results[full_name]))
    return results
