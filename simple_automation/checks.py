def check_valid_dir(path):
    if not path:
        raise Error("Path must be non-empty")
    if path[0] != "/":
        raise Error("Path must be absolute")
