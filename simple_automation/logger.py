"""
Provides logging utilities.
"""

import argparse
from dataclasses import dataclass
import os
from typing import Any

from simple_automation import globals as G

@dataclass
class State:
    """Global state for logging."""

    indentation_level: int = 0
    """The current global indentation level."""

state = State()
"""The global logger state."""

def col(color_code: str) -> str:
    """Returns the given argument only if color is enabled."""
    if not isinstance(G.args, argparse.Namespace):
        use_color = os.getenv("NO_COLOR") is None
    else:
        use_color = not G.args.no_color

    return color_code if use_color else ""

class IndentationContext:
    """A context manager to modify the indentation level."""
    def __enter__(self):
        state.indentation_level += 1

    def __exit__(self, type_t, value, traceback):
        _ = (type_t, value, traceback)
        state.indentation_level -= 1

def ellipsis(s: str, width: int) -> str:
    """
    Shrinks the given string to width (including an ellipsis character).

    Parameters
    ----------
    s
        The string.
    width
        The maximum width.

    Returns
    -------
    str
        A modified string with at most `width` characters.
    """
    if len(s) > width:
        s = s[:width - 1] + "…"
    return s

def indent() -> IndentationContext:
    """Retruns a context manager that increases the indentation level."""
    return IndentationContext()

def indent_prefix() -> str:
    """Returns the indentation prefix for the current indentation level."""
    return "  " * state.indentation_level

def print_indented(msg, **kwargs):
    """Same as print(), but prefixes the message with the indentation prefix."""
    print(f"{indent_prefix()}{msg}", **kwargs)


def connection_init(connector):
    """Prints connection initialization information."""
    print_indented(f"{col('[1;34m')}{connector.schema}{col('[m')} connecting... ", end="", flush=True)

def connection_failed(error_msg: str):
    """Signals that an error has occurred while establishing the connection."""
    print(col("[1;31m") + "ERR" + col("[m"))
    print_indented(f" {col('[37m')}└{col('[m')} " + f"{col('[31m')}{error_msg}{col('[m')}")

def connection_established():
    """Signals that the connection has been successfully established."""
    print(col("[1;32m") + "OK" + col("[m"))


def run_script(script, name=None):
    """Prints the script file and name that is being executed next."""
    if name is not None:
        print_indented(f"{col('[33;1m')}script{col('[m')} {script} {col('[37m')}({name}){col('[m')}")
    else:
        print_indented(f"{col('[33;1m')}script{col('[m')} {script}")

def print_operation_title(op, title_color, end="\n"):
    """Prints the operation title and description."""
    name_if_given = (" " + col('[37m') + f"({op.name})" + col('[m')) if op.name is not None else ""
    print_indented(f"{title_color}{op.op_name}{col('[m')} {op.description}{name_if_given}", end=end, flush=True)

def print_operation_early(op):
    """Prints the operation title and description before the final status is known."""
    title_color = col("[1;33m")
    print_operation_title(op, title_color, end="")

def print_operation(op, result):
    """Prints the operation summary after it has finished execution."""
    # TODO: make inventory.py able to set verbose=3 without needing to do -v everytime
    if result.success:
        title_color = col("[1;32m") if result.changed else col("[1m")
    else:
        title_color = col("[1;31m")

    # Print title and name, overwriting the transitive status
    print("\r", end="")
    print_operation_title(op, title_color)

    if not result.success:
        print_indented(f" {col('[37m')}└{col('[m')} " + f"{col('[31m')}{result.failure_message}{col('[m')}")
        return

    if not G.args.changes:
        return

    # Print key: value pairs with changes
    state_infos = []
    for k,final_v in result.final.items():
        initial_v = result.initial[k]

        def to_str(v: Any) -> str:
            return v.hex() if isinstance(v, bytes) else str(v)

        # Add ellipsis on long strings
        str_k = ellipsis(k, 12)
        str_initial_v = ellipsis(to_str(initial_v), 9)
        str_final_v = ellipsis(to_str(final_v), 9+3+9 if initial_v is None else 9)

        if initial_v == final_v:
            if G.args.verbose >= 1:
                # TODO = instead of : for better readability
                entry_str = f"{col('[37m')}{str_k}: {str_initial_v}{col('[m')}"
                state_infos.append(entry_str)
        else:
            if initial_v is None:
                entry_str = f"{col('[33m')}{str_k}: {col('[32m')}{str_final_v}{col('[m')}"
            else:
                entry_str = f"{col('[33m')}{str_k}: {col('[31m')}{str_initial_v}{col('[33m')} → {col('[32m')}{str_final_v}{col('[m')}"
            state_infos.append(entry_str)

    if len(state_infos) > 0:
        print_indented(f" {col('[37m')}└{col('[m')} " + f"{col('[37m')},{col('[m')} ".join(state_infos))
