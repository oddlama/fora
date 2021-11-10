"""
Provides logging utilities.
"""

from typing import Any

# pylint: disable=cyclic-import
# Cyclic import is correct at this point, as this module will not access anything from simple_automation
# when it is being loaded, but only when certain functions are used.
import simple_automation
from simple_automation.utils import col

class IndentationContext:
    """A context manager to modify the indentation level."""
    def __init__(self, logger):
        self.logger = logger

    def __enter__(self):
        self.logger.indentation_level += 1

    def __exit__(self, type_t, value, traceback):
        _ = (type_t, value, traceback)
        self.logger.indentation_level -= 1

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

class Logger:
    def __init__(self):
        self.indentation_level = 0

    def indent(self):
        return IndentationContext(self)

    def connection_init(self, connector):
        print(f"{col('[1;34m')}{connector.schema}{col('[m')} connecting... ", end="", flush=True)

    def connection_failed(self, error_msg: str):
        print(col("[1;31m") + "ERR" + col("[m"))
        self.print(f" {col('[37m')}└{col('[m')} " + f"{col('[31m')}{error_msg}{col('[m')}")

    def connection_established(self):
        print(col("[1;32m") + "OK" + col("[m"))

    def indent_prefix(self):
        ret = ""
        for _ in range(self.indentation_level):
            ret += "  "
        return ret

    def print(self, msg):
        print(f"{self.indent_prefix()}{msg}")

    def warn(self, msg):
        print(f"{self.indent_prefix()}{col('[33m')}WARN:{col('[m')} {msg}")

    def error(self, msg):
        print(f"[ ERROR ] {msg}")

    def skip_host(self, host, msg):
        print(f"[ SKIP ] Skipping host {host.name}: {msg}")

    def run_script(self, script, name=None):
        if name is not None:
            print(f"{self.indent_prefix()}{col('[33;1m')}script{col('[m')} {script} {col('[37m')}({name}){col('[m')}")
        else:
            print(f"{self.indent_prefix()}{col('[33;1m')}script{col('[m')} {script}")

    def print_operation_title(self, op, title_color, end="\n"):
        """
        Prints the operation title and desc
        """
        name_if_given = (" " + col('[37m') + f"({op.name})" + col('[m')) if op.name is not None else ""
        print(f"{self.indent_prefix()}{title_color}{op.op_name}{col('[m')} {op.description}{name_if_given}", end=end, flush=True)

    def print_operation_early(self, op):
        """
        Prints the op summary early (i.e. without changes)
        """
        title_color = col("[1;33m")
        self.print_operation_title(op, title_color, end="")

    def print_operation(self, op, result):
        """
        Prints the operation summary
        """
        # TODO: make inventory.py able to set verbose=3 without needing to do -v everytime
        if result.success:
            if result.changed:
                title_color = col("[1;32m")
            else:
                title_color = col("[1m")
        else:
            title_color = col("[1;31m")

        # Print title and name, overwriting the transitive status
        print("\r", end="")
        self.print_operation_title(op, title_color)

        if result.success:
            if simple_automation.args.changes:
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
                        if simple_automation.args.verbose >= 1:
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
                    self.print(f" {col('[37m')}└{col('[m')} " + f"{col('[37m')},{col('[m')} ".join(state_infos))
        else:
            self.print(f" {col('[37m')}└{col('[m')} " + f"{col('[31m')}{result.failure_message}{col('[m')}")
