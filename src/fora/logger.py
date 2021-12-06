"""
Provides logging utilities.
"""

import argparse
import difflib
import os
from dataclasses import dataclass
import sys
from types import TracebackType
from typing import Any, Optional, Type, cast

from fora import globals as G

@dataclass
class State:
    """Global state for logging."""

    indentation_level: int = 0
    """The current global indentation level."""

state: State = State()
"""The global logger state."""

def col(color_code: str) -> str:
    """Returns the given argument only if color is enabled."""
    if not isinstance(cast(Any, G.args), argparse.Namespace):
        use_color = os.getenv("NO_COLOR") is None
    else:
        use_color = not G.args.no_color

    return color_code if use_color else ""

class IndentationContext:
    """A context manager to modify the indentation level."""
    def __enter__(self) -> None:
        state.indentation_level += 1

    def __exit__(self, exc_type: Optional[Type[BaseException]], exc: Optional[BaseException], traceback: Optional[TracebackType]) -> None:
        _ = (exc_type, exc, traceback)
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

def debug(msg: str) -> None:
    """Prints the given message only in debug mode."""
    if not G.args.debug:
        return

    print(f"   [1;34mDEBUG[m: {msg}", file=sys.stderr)

def debug_args(msg: str, args: dict[str, Any]) -> None:
    """Prints all given arguments when in debug mode."""
    if not G.args.debug:
        return

    str_args = ""
    args = {k: v for k,v in args.items() if k != "self"}
    if len(args) > 0:
        str_args = " " + ", ".join(f"{k}={v}" for k,v in args.items())

    print(f"   [1;34mDEBUG[m: {msg}{str_args}", file=sys.stderr)

def print_indented(msg: str, **kwargs: Any) -> None:
    """Same as print(), but prefixes the message with the indentation prefix."""
    print(f"{indent_prefix()}{msg}", **kwargs)


def connection_init(connector: Any) -> None:
    """Prints connection initialization information."""
    print_indented(f"{col('[1;34m')}{connector.schema}{col('[m')} connecting... ", end="", flush=True)

def connection_failed(error_msg: str) -> None:
    """Signals that an error has occurred while establishing the connection."""
    print(col("[1;31m") + "ERR" + col("[m"))
    print_indented(f" {col('[37m')}└{col('[m')} " + f"{col('[31m')}{error_msg}{col('[m')}")

def connection_established() -> None:
    """Signals that the connection has been successfully established."""
    print(col("[1;32m") + "OK" + col("[m"))


def run_script(script: str, name: Optional[str] = None) -> None:
    """Prints the script file and name that is being executed next."""
    if name is not None:
        print_indented(f"{col('[33;1m')}script{col('[m')} {script} {col('[37m')}({name}){col('[m')}")
    else:
        print_indented(f"{col('[33;1m')}script{col('[m')} {script}")

def print_operation_title(op: Any, title_color: str, end: str = "\n") -> None:
    """Prints the operation title and description."""
    name_if_given = (" " + col('[37m') + f"({op.name})" + col('[m')) if op.name is not None else ""
    dry_run_info = f" {col('[37m')}(dry){col('[m')}" if G.args.dry else ""
    print_indented(f"{title_color}{op.op_name}{col('[m')}{dry_run_info} {op.description}{name_if_given}", end=end, flush=True)

def print_operation_early(op: Any) -> None:
    """Prints the operation title and description before the final status is known."""
    title_color = col("[1;33m")
    # Only overwrite status later if debugging is not enabled.
    print_operation_title(op, title_color, end=" (early status)\n" if G.args.debug else "")


def decode_escape(data: bytes, encoding: str = 'utf-8') -> str:
    """
    Tries to decode the given data with the given encoding, but replaces all non-decodeable
    and non-printable characters with backslash escape sequences.

    Example:

        >>> decode_escape(b'It is Wednesday\\nmy dudes\\r\\n🐸\\xff\\0')
        'It is Wednesday\\\\nMy Dudes\\\\r\\\\n🐸\\\\xff\\\\0'

    Parameters
    ----------
    content
        The content that should be decoded and escaped.
    encoding
        The encoding that should be tried. To preserve utf-8 symbols, use 'utf-8',
        to replace any non-ascii character with an escape sequence use 'ascii'.

    Returns
    -------
    str
        The decoded and escaped string.
    """
    def escape_char(c: str) -> str:
        special = {'\x00': '\\0', '\n': '\\n', '\r': '\\r', '\t': '\\t'}
        if c in special:
            return special[c]

        num = ord(c)
        if not c.isprintable() and num <= 0xff:
            return f"\\x{num:02x}"
        return c
    return ''.join([escape_char(c) for c in data.decode(encoding, 'backslashreplace')])

def diff(filename: str, old: Optional[bytes], new: Optional[bytes], color: bool = True) -> list[str]:
    """
    Creates a diff between the old and new content of the given filename,
    that can be printed to the console. This function returns the diff
    output as an array of lines. The lines in the output array are not
    terminated by newlines.

    If color is True, the diff is colored using ANSI escape sequences.

    If you want to provide an alternative diffing function, beware that
    the input can theoretically contain any bytes and therefore should
    be decoded as utf-8 if possible, but non-decodeable
    or non-printable charaters should be replaced with human readable
    variants such as `\\x00`, `^@` or similar represenations.

    Your diffing function should still be able to work on the raw bytes
    representation, after you aquire the diff and before you apply colors,
    your output should be made printable with a function such as `fora.logger.decode_escape`:

        # First decode and escape
        line = logger.decode_escape(byteline)
        # Add coloring afterwards so ANSI escape sequences are not escaped

    Parameters
    ----------
    filename
        The filename of the file that is being diffed.
    old
        The old content, or None if the file didn't exist before.
    new
        The new content, or None if the file was deleted.
    color
        Whether the output should be colored (with ANSI color sequences).

    Returns
    -------
    list[str]
        The lines of the diff output. The individual lines will not have a terminating newline.
    """
    bdiff = list(difflib.diff_bytes(difflib.unified_diff,
                        a=[] if old is None else old.split(b'\n'),
                        b=[] if new is None else new.split(b'\n'),
                        lineterm=b''))
    # Strip file name header and decode diff to be human readable.
    difflines = map(decode_escape, bdiff[2:])

    # Create custom file name header
    action = 'created' if old is None else 'deleted' if new is None else 'modified'
    title = f"{action}: {filename}"
    N = len(title)
    header = ['─' * N, title, '─' * N]

    # Apply coloring if desired
    if color:
        def apply_color(line: str) -> str:
            linecolor = {
                '+': '[32m',
                '-': '[31m',
                '@': '[34m',
            }
            return linecolor.get(line[0], '[37m') + line + '[m'
        # Apply color to diff
        difflines = map(apply_color, difflines)
        # Apply color to header
        header = list(map(lambda line: f"[33m{line}[m", header))

    return header + list(difflines)

# TODO: move functions to operation api. cleaner and has type access.
def _operation_state_infos(result: Any) -> list[str]:
    def to_str(v: Any) -> str:
        return v.hex() if isinstance(v, bytes) else str(v)

    # Print "key: value" pairs with changes
    state_infos: list[str] = []
    for k,final_v in result.final.items():
        if final_v is None:
            continue

        initial_v = result.initial[k]
        str_initial_v = to_str(initial_v)
        str_final_v = to_str(final_v)

        # Add ellipsis on long strings, if we are not in verbose mode
        if G.args.verbose == 0:
            k = ellipsis(k, 12)
            str_initial_v = ellipsis(to_str(initial_v), 9)
            str_final_v = ellipsis(to_str(final_v), 9+3+9 if initial_v is None else 9)

        if initial_v == final_v:
            if G.args.verbose >= 1:
                # TODO = instead of : for better readability
                entry_str = f"{col('[37m')}{k}: {str_initial_v}{col('[m')}"
                state_infos.append(entry_str)
        else:
            if initial_v is None:
                entry_str = f"{col('[33m')}{k}: {col('[32m')}{str_final_v}{col('[m')}"
            else:
                entry_str = f"{col('[33m')}{k}: {col('[31m')}{str_initial_v}{col('[33m')} → {col('[32m')}{str_final_v}{col('[m')}"
            state_infos.append(entry_str)
    return state_infos

def print_operation(op: Any, result: Any) -> None:
    """Prints the operation summary after it has finished execution."""
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

    # Cache number of upcoming diffs to determine what box character to print
    n_diffs = len(op.diffs) if G.args.diff else 0
    box_char = '└' if n_diffs == 0 else '├'

    # Print "key: value" pairs with changes
    state_infos = _operation_state_infos(result)
    if len(state_infos) > 0:
        print_indented(f"{col('[37m')}{box_char}{col('[m')} " + f"{col('[37m')},{col('[m')} ".join(state_infos))

    if G.args.diff:
        diff_lines = []
        # Generate diffs
        for file, old, new in op.diffs:
            diff_lines.extend(diff(file, old, new))
        # Print diffs with block character line
        if len(diff_lines) > 0:
            for l in diff_lines[:-1]:
                print_indented("│ " + l)
            print_indented("└ " + diff_lines[-1])
