"""
Provides utility functions.
"""

import sys

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
    """
    while True:
        print(f"{msg} (Y/n) ", end="", flush=True)
        choice = input().lower()
        if choice in ["", "y", "yes"]:
            return True
        if choice in ["n", "no"]:
            return False

        print(f"Response '{choice}' not understood.")
