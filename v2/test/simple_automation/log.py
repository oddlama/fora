"""
Provides logging utilities.
"""

from simple_automation.utils import col

class IndentationContext:
    """
    A context manager to modify the indentation level.
    """
    def __init__(self, logger):
        self.logger = logger

    def __enter__(self):
        self.logger.indentation_level += 1

    def __exit__(self, type_t, value, traceback):
        self.logger.indentation_level -= 1

class ConnectionLogger:
    def __init__(self, host, connector):
        self.host = host
        self.connector = connector

    def init(self):
        print(f"{col('[1;34m')}{self.connector.schema}{col('[m')} connecting... ", end="", flush=True)

    def established(self):
        print(col("[1;32m") + "OK" + col("[m"))

    def requested_close(self):
        pass
        #print(f"[ CONN ] Requesting to close connection to {self.host.name}")

    def closed(self):
        pass
        #print(f"[ CONN ] Connection to {self.host.name} closed")

    def failed(self, msg):
        pass
        #print(f"[ CONN ] Connection to {self.host.name} failed: {msg}")

    def error(self, msg):
        pass
        #print(f"[ CONN ] Connection error on {self.host.name}: {msg}")

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

class Logger:
    def __init__(self):
        self.connections = {}
        self.indentation_level = 0

    def indent(self):
        return IndentationContext(self)

    def new_connection(self, host, connector):
        cl = ConnectionLogger(host, connector)
        self.connections[host] = cl
        return cl

    def indent_prefix(self):
        ret = ""
        for i in range(self.indentation_level):
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
        print(f"{self.indent_prefix()}{title_color}{op.op_name}{col('[m')} {op.description} {col('[37m')}({op.name}){col('[m')}", end=end, flush=True)

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
        # TODO make inventory.py able to set verbose=3 without needing to do -v everytime
        # TODO format proposal:
        # normal:
        #   dir /tmp/very/special/dir (This is some directory that needs creation)
        # -c:
        #   dir /tmp/very/special/dir (This is some directory that needs creation)
        #   └ exists: False → True, mode: 755, sha: 84rghuir.. -> 4grethiu..
        #   dir /tmp/very/special/dir (This is some directory that needs creation)
        #   └ exists: True, mode: 755
        # -c --diff:
        #   dir /tmp/very/special/dir (This is some directory that needs creation)
        #   ├ exists: False → True, mode: 755, sha: 84rghuir.. -> 4grethiu..
        #   └ diff
        #     | /(thgrbrp/tkrgfr
        #     | -a
        #     | +b
        # -cv:
        #   dir /tmp/very/special/dir (This is some directory that needs creation)
        #   ├ exists: False → True
        #   ├ sha: 84rghuir3ru09wjgrgiu3ho -> 4grethiugrr380u8rhuir3wgr
        #   └ mode: mode: 755
        #   dir /tmp/very/special/dir (This is some directory that needs creation)
        #   └ fail: error message
        verbose = True # TODO
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
            # Print key: value pairs with changes
            state_infos = []
            for k,final_v in result.final.items():
                initial_v = result.initial[k]

                # Add ellipsis on long strings
                str_k = ellipsis(k, 12)
                str_initial_v = ellipsis(str(initial_v), 9)
                str_final_v = ellipsis(str(final_v), 9+3+9 if initial_v is None else 9)

                if initial_v == final_v:
                    if verbose >= 1:
                        # TODO = instead of : for better readability
                        entry_str = f"{col('[37m')}{str_k}: {str_initial_v}{col('[m')}"
                        state_infos.append(entry_str)
                else:
                    if initial_v is None:
                        entry_str = f"{col('[33m')}{str_k}: {col('[32m')}{str_final_v}{col('[m')}"
                    else:
                        entry_str = f"{col('[33m')}{str_k}: {col('[31m')}{str_initial_v}{col('[33m')} → {col('[32m')}{str_final_v}{col('[m')}"
                    state_infos.append(entry_str)
            print(f"{col('[37m')},{col('[m')} ".join(state_infos))
        else:
            print(f"{col('[31m')}{result.failure_message}{col('[m')}")

        #if verbose >= 1 and op.extra_info is not None:
        #    extra_infos = []
        #    for k,v in op.extra_info.items():
        #        extra_infos.append(f"[37m{str(k)}: {str(v)}[m")
        #    print(" " * 15 + "[37m,[m ".join(extra_infos))
