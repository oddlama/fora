from simple_automation.exceptions import LogicError

def check_valid_key(key):
    if not key:
        raise LogicError(f"Invalid empty key")
    if '..' in key or not key.replace('.', '').isidentifier():
        raise LogicError(f"Invalid key: '{key}' is not a valid identifier")

def check_valid_dir(path):
    if not path:
        raise Error("Path must be non-empty")
    if path[0] != "/":
        raise Error("Path must be absolute")
