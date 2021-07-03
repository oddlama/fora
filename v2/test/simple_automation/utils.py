"""
Provides utility functions.
"""

import sys
import uuid
from typing import TypeVar, Callable

import importlib.machinery
import importlib.util

T = TypeVar('T')

def print_warning(msg: str):
    """
    Prints a message with a colored 'warning: ' prefix.
    """
    print(f"[1;33mwarning:[m {msg}")

def print_error(msg: str):
    """
    Prints a message with a colored 'error: ' prefix.
    """
    print(f"[1;31merror:[m {msg}")

def die_error(msg: str, status_code=1):
    """
    Prints a message with a colored 'error: ' prefix, and exit with the given status code afterwards.
    """
    print_error(msg)
    sys.exit(status_code)

class CycleError(ValueError):
    def __init__(self, msg, cycle):
        """
        This error is thrown when a cycle is detected in a graph, and
        the throwing function can't deal with cyclic graphs.
        """
        super().__init__(msg)
        self.cycle = cycle

def load_py_module(file: str, print_on_error=True):
    """
    Loads a module from the given filename and assigns a unique module name to it.
    Calling this function twice for the same file will yield distinct instances.
    """
    module_id = str(uuid.uuid4()).replace('-', '_')
    loader = importlib.machinery.SourceFileLoader(f"__simple_automation_dynamic_module_{module_id}", file)
    spec = importlib.util.spec_from_loader(loader.name, loader)
    if spec is None:
        raise ValueError(f"Failed to load module from file '{file}'")
    mod = importlib.util.module_from_spec(spec)
    try:
        loader.exec_module(mod)
    except Exception as e:
        if print_on_error:
            print_error(f"An exception occurred while loading module '{file}'!")
        raise e
    return mod

def merge_dicts(source, destination):
    """
    Recursively merges two dictionaries source and destination.
    The source dictionary will only be read, but the destination dictionary will be overwritten.
    """
    for key, value in source.items():
        if isinstance(value, dict):
            # get node or create one
            node = destination.setdefault(key, {})
            merge_dicts(value, node)
        else:
            destination[key] = value

    return destination

def align_ellipsis(s, width):
    """
    Shrinks the given string to width (including an ellipsis character),
    and additionally pads the string with spaces to match the given with.
    """
    if len(s) > width:
        s = s[:width - 1] + "…"
    return f"{s:<{width}}"

def ellipsis(s, width):
    """
    Shrinks the given string to width (including an ellipsis character).
    """
    if len(s) > width:
        s = s[:width - 1] + "…"
    return s

def print_transaction_title(transaction, title_color, status_char):
    """
    Prints the transaction title and name
    """
    title = align_ellipsis(transaction.title, 10)
    name_align_at = 30 * (1 + (len(transaction.name) // 30))
    name = f"{transaction.name:<{name_align_at}}"
    print(f"[{status_char}] {title_color}{title}[m {name}", end="", flush=True)

def print_transaction_early(transaction):
    """
    Prints the transaction summary early (i.e. without changes)
    """
    title_color = "[1;33m"
    status_char = "[33m?[m"

    # Print title and name
    print_transaction_title(transaction, title_color, status_char)

def print_transaction(context, transaction):
    """
    Prints the transaction summary
    """
    if transaction.success:
        if transaction.changed:
            title_color = "[1;34m"
            status_char = "[32m+[m"
        else:
            title_color = "[1m"
            status_char = "[37m.[m"
    else:
        title_color = "[1;31m"
        status_char = "[1;31m![m"

    # Print title and name, overwriting the transitive status
    print("\r", end="")
    print_transaction_title(transaction, title_color, status_char)

    # Print key: value pairs with changes
    state_infos = []
    for k,final_v in transaction.final_state.items():
        initial_v = transaction.initial_state[k]

        # Add ellipsis on long strings
        str_k = ellipsis(k, 12)
        str_initial_v = ellipsis(str(initial_v), 9)
        str_final_v = ellipsis(str(final_v), 9+3+9 if initial_v is None else 9)

        if initial_v == final_v:
            if context.verbose >= 1:
                entry_str = f"[37m{str_k}: {str_initial_v}[m"
                state_infos.append(entry_str)
        else:
            if initial_v is None:
                entry_str = f"[33m{str_k}: [32m{str_final_v}[m"
            else:
                entry_str = f"[33m{str_k}: [31m{str_initial_v}[33m → [32m{str_final_v}[m"
            state_infos.append(entry_str)
    print("[37m,[m ".join(state_infos))

    if context.verbose >= 1 and transaction.extra_info is not None:
        extra_infos = []
        for k,v in transaction.extra_info.items():
            extra_infos.append(f"[37m{str(k)}: {str(v)}[m")
        print(" " * 15 + "[37m,[m ".join(extra_infos))

def choice_yes(msg: str) -> bool:
    """
    Awaits user choice (Y/n).

    Parameters
    ----------
    msg : str
        The message to print.

    Returns
    -------
    bool
        True if the choice was yes, False otherwise.
    """
    while True:
        print(f"{msg} (Y/n) ", end="", flush=True)
        choice = input().lower()
        if choice in ["", "y", "yes"]:
            return True
        if choice in ["n", "no"]:
            return False

        print(f"Response '{choice}' not understood.")

def rank_sort(vertices: list[T], preds_of: Callable[[T], list[T]], childs_of: Callable[[T], list[T]]) -> dict[T, int]:
    """
    Calculates the top-down rank for each vertex. Supports graphs with multiple components.
    The graph must not have any cycles. If it does, a CycleError might be thrown, but this
    is not guaranteed and can also result in the resulting rank containing back-edges.
    By checking if the rank assignment contains a back-edge, a cycle in the graph can be detected
    retroactively.

    Parameters
    ----------
    vertices : list[T]
        A list of vertices
    preds_of : Callable[[T], list[T]]
        A function that returns a list of predecessors given a vertex
    childs_of : Callable[[T], list[T]]
        A function that returns a list of successors given a vertex

    Returns
    -------
    dict[T, int]
        A dict associating a rank to each vertex
    """
    # FIXME in description: must be cycle free already. Might detect cycle when
    # searching for root node, but this is not guaranteed to detect any cycle.

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
        while len(preds_of(root)) > 0:
            root = preds_of(root)[0]
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
