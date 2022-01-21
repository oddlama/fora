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
import shutil
import sys
import traceback
import uuid
from types import ModuleType, TracebackType
from typing import Any, Collection, NoReturn, Type, TypeVar, Callable, Iterable, Optional, Union

import fora
from fora import globals as G
from fora.types import GroupWrapper, HostWrapper, ScriptWrapper
from fora.logger import col

class FatalError(Exception):
    """An exception type for fatal errors, optionally including a file location."""
    def __init__(self, msg: str, loc: Optional[str] = None):
        super().__init__(msg)
        self.loc = loc

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

def print_status(status: str, msg: str) -> None:
    """Prints a message with a (possibly colored) status prefix."""
    print(f"{col('[1;32m')}{status}{col('[m')} {msg}")

def print_warning(msg: str) -> None:
    """Prints a message with a (possibly colored) 'warning: ' prefix."""
    print(f"{col('[1;33m')}warning:{col('[m')} {msg}")

def print_error(msg: str, loc: Optional[str] = None) -> None:
    """Prints a message with a (possibly colored) 'error: ' prefix."""
    if loc is None:
        print(f"{col('[1;31m')}error:{col('[m')} {msg}", file=sys.stderr)
    else:
        print(f"{col('[1m')}{loc}: {col('[1;31m')}error:{col('[m')} {msg}", file=sys.stderr)

def len_ignore_leading_ansi(s: str) -> int:
    """Returns the length of the string or 0 if it starts with `\033[`"""
    return 0 if s.startswith("\033[") else len(s)

def ansilen(ss: Collection[str]) -> int:
    """Returns the length of all strings combined ignoring ansi control sequences"""
    return sum(map(len_ignore_leading_ansi, ss))

def ansipad(ss: Collection[str], pad: int = 0) -> str:
    """Joins an array of string and ansi codes together and pads the result with spaces to at least `pad` characters."""
    return ''.join(ss) + " " * max(0, pad - ansilen(ss))

def print_fullwith(left: Optional[list[str]] = None, right: Optional[list[str]] = None, pad: str = '─', **kwargs: Any) -> None:
    """Prints a message padded to the terminal width to stderr."""
    if not left:
        left = []
    if not right:
        right = []

    cols = max(shutil.get_terminal_size((80, 20)).columns, 80)
    n_pad = max(0, (cols - ansilen(left) - ansilen(right)))
    print(''.join(left) + pad * n_pad + ''.join(right), **kwargs)

def print_table(header: Collection[Collection[str]], rows: Collection[Collection[Collection[str]]], box_color: str = "\033[90m", min_col_width: Optional[list[int]] = None) -> None:
    """Prints the given rows as an ascii box table."""
    max_col_width = 40
    terminal_cols = max(shutil.get_terminal_size((80, 20)).columns, 80)

    # Calculate max needed with for each column
    cols = len(header)
    max_value_width = [0] * cols
    for i,v in enumerate(header):
        max_value_width[i] = max(max_value_width[i], ansilen(v))
    for row in rows:
        for i,v in enumerate(row):
            max_value_width[i] = max(max_value_width[i], ansilen(v))

    # Fairly distribute space between columns
    if min_col_width is None:
        min_col_width = [0] * cols
    even_col_width = terminal_cols // cols
    chars_needed_for_table_boxes = 3 * (len(header) - 1)
    available_space = terminal_cols - chars_needed_for_table_boxes
    col_width = [max(min_col_width[i], min(max_col_width, w, available_space - (cols - i - 1) * even_col_width)) for i,w in enumerate(max_value_width)]

    # Distribute remaining space to first column from the back that would need the space
    total_width = sum(col_width)
    rest = available_space - total_width
    if rest > 0:
        for i,w in reversed(list(enumerate(max_value_width))):
            if w > col_width[i]:
                col_width[i] += rest
                break

    # Print table
    col_reset = col("\033[m")
    col_box = col(box_color)
    delim = col_box + " │ " + col_reset
    print(delim.join([ansipad(col, w) for col,w in zip(header, col_width)]))
    print(col_box + "─┼─".join(["─" * w for w in col_width]) + col_reset)
    for row in rows:
        print(delim.join([ansipad(col, w) for col,w in zip(row, col_width)]))

def die_error(msg: str, loc: Optional[str] = None, status_code: int = 1) -> NoReturn:
    """Prints a message with a colored 'error: ' prefix, and exit with the given status code afterwards."""
    print_error(msg, loc=loc)
    sys.exit(status_code)

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
    The graph must not have any cycles or a CycleError will be thrown.

    Parameters
    ----------
    vertices
        A list of vertices
    preds_of
        A function that returns a list of predecessors given a vertex
    childs_of
        A function that returns a list of successors given a vertex

    Raises
    ------
    CycleError
        The given graph is cyclic.

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

    # Find cycles in dependencies by checking for the existence of any edge
    # that doesn't increase the rank. This is an error.
    for v in vertices:
        for c in childs_of(v):
            if ranks[c] <= ranks[v]:
                raise CycleError(f"Cannot apply rank_sort to cyclic graph (late detection).", [c, v])

    return ranks

def script_trace(script_stack: list[tuple[ScriptWrapper, inspect.FrameInfo]],
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

def is_normal_var(attr: str, value: Any) -> bool:
    """Returns True if the attribute doesn't start with an underscore, and is not a module."""
    return not attr.startswith("_") \
            and not isinstance(value, ModuleType)

# We need a way to allow groups and host modules to override variables from other
# low precedence groups, or to extend a dictionary, list or some other object defined
# previously. How do we accomplish this?
#
# One approach that I tried was to implement a fully hierarchical lookup for the
# host module that did go through all groups in reverse order of precedence and return the
# as soon as a variable was defined on one of the modules. Apart from the complexity,
# a problem with this approach was that modifying existing variables like dictionaries from
# parent modules wasn't easy or clean. We would've had to distinguish between those cases
# depending on a type annotation of the variable. While this was possible, it introduced
# an unnecessary conecept of annotating some variables to gain special "magic" behavior
# and a lot of complexity. At that time, the depndencies between modules was defined in
# the modules themselves, which made it impossible to inherit variables between groups.
#
# The approach I settled on now is to define groups and group dependencies in the inventory,
# allowing us to load group modules in the correct order. By doing this, we can bequest (copy)
# all variables that have been defined until that point to the next module that will be loaded,
# be it a host or another group. This allows any module to access and modify all inherited
# variables easily, as they are just part of the global variables.
#
# This reduces the special "fora" behavior to this list of things:
#   - script parameters are defined via a "params" dataclass
#   - all attributes are defined on the host in question, but script default variables
#     still require minimal hijacking of getattr
#   - inventories, groups and hosts are collections of global variables used within fora
def host_getattr_hierarchical(host: HostWrapper, attr: str) -> Any:
    """
    Looks up and returns the given attribute on the host's hierarchy in the following order:

      1. Host variables
      2. Group variables (respecting topological order, excluding GroupWrapper variables)
      3. Script variables (excluding ScriptWrapper variables)
      4. raises AttributeError

    If the attribute starts with an underscore, the lookup will always be from the host object
    itself, and won't be propagated hierarchically. The same is True for any variable that
    is a module (so imported modules in group/script definitions will not be visible).

    Parameters
    ----------
    host
        The host for which the attribute should be retrieved.
    attr
        The attribute to retrieve.

    Returns
    -------
    Any
        The attribute's value if it was found.

    Raises
    ------
    AttributeError
        The given attribute was not found.
    """
    # While getattr implicitly does a local lookup before calling this function,
    # we still need this block to force certain variables to always be looked up locally.
    if attr.startswith("_") or attr in HostWrapper.__annotations__:
        if attr not in vars(host):
            raise AttributeError(attr)
        return vars(host)[attr]

    if attr not in GroupWrapper.__annotations__ and attr not in GroupWrapper.__dict__:
        # Look up variable on groups
        for g in G.group_order:
            # Only consider a group if the host is in that group
            if g not in vars(host)["groups"]:
                continue

            # Return the attribute if it is set on the group,
            # and if it is a normal variable
            group = G.groups[g]
            if hasattr(group, attr):
                value = getattr(group, attr)
                if is_normal_var(attr, value):
                    return value

    if attr not in ScriptWrapper.__annotations__ and attr not in ScriptWrapper.__dict__:
        # Look up variable on current script
        # pylint: disable=protected-access,import-outside-toplevel,cyclic-import
        if fora.script is not None:
            if hasattr(fora.script, attr):
                value = getattr(fora.script, attr)
                if is_normal_var(attr, value):
                    return value

    raise AttributeError(attr)

def host_vars_hierarchical(host: HostWrapper, include_all_host_variables: bool = False, include_definition: bool = False) -> dict[str, Any]:
    """
    Functions similarly to a hierarchical equivalent of `vars()`, just as
    `host_getattr_hierarchical` is the hierarchical equivalent of `getattr`.
    The same constraints as for `host_getattr_hierarchical` apply, but never raises
    an AttributeError.

    Parameters
    ----------
    host
        The host for which all variables should be collected.
    include_all_host_variables
        Whether to include all host variables that `var(host)` yields (also hidden and special variables such as __getattr__, or imported modules).
    include_definition
        Wrap each `value` in a tuple `(value, definition)` and also return from where the variable originates.

    Returns
    -------
    dict[str, Any]
        A dictionary containing all currently accessible variables.
    """
    # We will add variables from bottom-up so that low-priority
    # variables can be overwritten as expected.
    dvars: dict[str, Any] = {}

    # First, add all variable from the current script
    # pylint: disable=protected-access,import-outside-toplevel,cyclic-import
    if fora.script is not None:
        # Add variables from the script that are neither private
        # nor part of a script's standard variables (ScriptWrapper.__annotations__ / __dict__)
        dvars.update({attr: (v, fora.script) for attr,v in vars(fora.script).items() if is_normal_var(attr, v)
                and attr not in ScriptWrapper.__annotations__
                and attr not in ScriptWrapper.__dict__})

    # Add variable from groups (reverse order so that the highest-priority
    # group overwrites variables from lower priorities.
    for g in reversed(G.group_order):
        # Only consider a group if the host is in that group
        if g not in vars(host)["groups"]:
            continue

        # Add variables from groups that are neither private
        # nor part of a group's standard variables (GroupWrapper.__annotations__)
        group = G.groups[g]
        dvars.update({attr: (v, group) for attr,v in vars(group).items() if is_normal_var(attr, v)
                and attr not in GroupWrapper.__annotations__
                and attr not in GroupWrapper.__dict__})

    # Lastly add all host variables, as they have the highest priority.
    dvars.update({attr: (v, host) for attr,v in vars(host).items() if include_all_host_variables or is_normal_var(attr, v)})

    # Strip definition if it isn't requested
    if not include_definition:
        dvars = {attr: v for attr,(v,_) in dvars.items()}

    return dvars

def transitive_dependencies(initial: set[T], relation: Callable[[T], set[T]]) -> set[T]:
    """
    Calculates all transitive dependencies given a set of inital nodes and a relation.

    Parameters
    ----------
    inital
        The initial nodes to calculate transitive dependencies for.
    relation
        A function that relates a `T` to a set of `T`s

    Returns
    -------
    set[T]
        The transitive dependencies
    """
    to_process = initial
    transitive_set = set()
    while len(to_process) > 0:
        t = to_process.pop()
        if t in transitive_set:
            continue

        transitive_set.add(t)
        to_process.update(relation(t))
    return transitive_set

def check_host_active() -> None:
    """Asserts that an inventory has been loaded and a host is active."""
    if not G.inventory_loaded:
        raise FatalError("Invalid attempt to call operation before inventory was loaded! Did you maybe swap the inventory and deploy file on the command line?")
    if fora.host is None:
        raise FatalError("Invalid attempt to call operation while no host is active!")
