class ConnectionLogger:
    def __init__(self, host, connector):
        self.host = host
        self.connector = connector

    def init(self):
        print(f"[ CONN ] Establishing connection to {self.host.name} via {self.connector.schema}")

    def established(self):
        print(f"[ CONN ] Connection to {self.host.name} established")

    def requested_close(self):
        print(f"[ CONN ] Requesting to close connection to {self.host.name}")

    def closed(self):
        print(f"[ CONN ] Connection to {self.host.name} closed")

    def failed(self, msg):
        print(f"[ CONN ] Connection to {self.host.name} failed: {msg}")

    def error(self, msg):
        print(f"[ CONN ] Connection error on {self.host.name}: {msg}")

class Logger:
    def __init__(self):
        self.connections = {}

    def new_connection(self, host, connector):
        cl = ConnectionLogger(host, connector)
        self.connections[host] = cl
        return cl

    def error(self, msg):
        print(f"[ ERROR ] {msg}")

    def skip_host(self, host, msg):
        print(f"[ SKIP ] Skipping host {host.name}: {msg}")

    def run_script(self, name, script):
        print(f"[ RUN ] {script}: {name}")

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
    title = align_ellipsis(transaction.op_name, 10)
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

def print_transaction(transaction, result):
    """
    Prints the transaction summary
    """
    verbose = True # TODO
    if result.success:
        if result.changed:
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
    for k,final_v in result.final.items():
        initial_v = result.initial[k]

        # Add ellipsis on long strings
        str_k = ellipsis(k, 12)
        str_initial_v = ellipsis(str(initial_v), 9)
        str_final_v = ellipsis(str(final_v), 9+3+9 if initial_v is None else 9)

        if initial_v == final_v:
            if verbose >= 1:
                entry_str = f"[37m{str_k}: {str_initial_v}[m"
                state_infos.append(entry_str)
        else:
            if initial_v is None:
                entry_str = f"[33m{str_k}: [32m{str_final_v}[m"
            else:
                entry_str = f"[33m{str_k}: [31m{str_initial_v}[33m → [32m{str_final_v}[m"
            state_infos.append(entry_str)
    print("[37m,[m ".join(state_infos))

    #if verbose >= 1 and transaction.extra_info is not None:
    #    extra_infos = []
    #    for k,v in transaction.extra_info.items():
    #        extra_infos.append(f"[37m{str(k)}: {str(v)}[m")
    #    print(" " * 15 + "[37m,[m ".join(extra_infos))
