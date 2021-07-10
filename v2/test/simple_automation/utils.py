"""
Provides utility functions
"""

import sys
import uuid
from typing import TypeVar, Callable, Iterable

import importlib.machinery
import importlib.util

T = TypeVar('T')

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
