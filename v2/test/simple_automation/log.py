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
        #print(f"[ CONN ] Establishing connection to {self.host.name} via {self.connector.schema}")
        #print(f"[1;34m{self.connector.schema}[m [1;33mconnecting[m")
        print(f"[1;34m{self.connector.schema}[m connecting... ", end="", flush=True)

    def established(self):
        #print(f"[ CONN ] Connection to {self.host.name} established")
        #print(f"[1;34m{self.connector.schema}[m [1;32mconnected[m")
        print("[1;32mOK[m")

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
        print(f"{self.indent_prefix()}[33mWARN:[m {msg}")

    def error(self, msg):
        print(f"[ ERROR ] {msg}")

    def skip_host(self, host, msg):
        print(f"[ SKIP ] Skipping host {host.name}: {msg}")

    def run_script(self, script, name=None):
        if name is not None:
            print(f"{self.indent_prefix()}[33;1mscript[m {script} [37m({name})[m")
        else:
            print(f"{self.indent_prefix()}[33;1mscript[m {script}")

    def print_transaction_title(self, transaction, title_color, status_char):
        """
        Prints the transaction title and desc
        """
        #title = align_ellipsis(transaction.op_name, 10)
        #name_align_at = 30 * (1 + (len(transaction.desc) // 30))
        #desc = f"{transaction.desc:<{name_align_at}}"
        title = transaction.op_name
        desc = transaction.description
        print(f"{self.indent_prefix()}{title_color}{title}[m {desc} ", end="", flush=True)

    def print_transaction_early(self, transaction):
        """
        Prints the transaction summary early (i.e. without changes)
        """
        title_color = "[1;33m"
        status_char = "[33m?[m"

        # Print title and name
        self.print_transaction_title(transaction, title_color, status_char)

    def print_transaction(self, transaction, result):
        """
        Prints the transaction summary
        """
        # TODO make inventory.py able to set verbose=3 without needing to do -v everytime
        # TODO format proposal:
        # normal:
        #   dir /tmp/very/special/dir (This is some directory that needs creation)
        # -v:
        #   dir /tmp/very/special/dir (This is some directory that needs creation)
        #   └ exists: False → True, mode: 755
        #   dir /tmp/very/special/dir (This is some directory that needs creation)
        #   └ exists: True, mode: 755
        # -vv:
        #   dir /tmp/very/special/dir (This is some directory that needs creation)
        #   ├ exists: False → True
        #   └ mode: mode: 755
        #   dir /tmp/very/special/dir (This is some directory that needs creation)
        #   └ fail: error message
        verbose = True # TODO
        if result.success:
            if result.changed:
                title_color = "[1;32m"
                status_char = "[1;32m+[m"
            else:
                title_color = "[1m"
                status_char = "[37m.[m"
        else:
            title_color = "[1;31m"
            status_char = "[1;31m![m"

        # Print title and name, overwriting the transitive status
        print("\r", end="")
        self.print_transaction_title(transaction, title_color, status_char)

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
                        entry_str = f"[37m{str_k}: {str_initial_v}[m"
                        state_infos.append(entry_str)
                else:
                    if initial_v is None:
                        entry_str = f"[33m{str_k}: [32m{str_final_v}[m"
                    else:
                        entry_str = f"[33m{str_k}: [31m{str_initial_v}[33m → [32m{str_final_v}[m"
                    state_infos.append(entry_str)
            print("[37m,[m ".join(state_infos))
        else:
            print(f"[31m{result.failure_message}[m")

        #if verbose >= 1 and transaction.extra_info is not None:
        #    extra_infos = []
        #    for k,v in transaction.extra_info.items():
        #        extra_infos.append(f"[37m{str(k)}: {str(v)}[m")
        #    print(" " * 15 + "[37m,[m ".join(extra_infos))
