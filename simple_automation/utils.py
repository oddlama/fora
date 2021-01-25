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
    if len(s) > width:
        s = s[:width - 1] + "…"
    return f"{s:<{width}}"

def ellipsis(s, width):
    if len(s) > width:
        s = s[:width - 1] + "…"
    return s
