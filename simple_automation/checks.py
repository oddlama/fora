from simple_automation.exceptions import LogicError

def check_valid_key(key, msg="Invalid key"):
    if not key:
        raise LogicError("Invalid empty key")
    if '..' in key or not key.replace('.', '').isidentifier():
        raise LogicError(f"{msg}: '{key}' is not a valid identifier")

def check_valid_path(path):
    if not path:
        raise LogicError("Path must be non-empty")
    if path[0] != "/":
        raise LogicError("Path must be absolute")

def check_valid_relative_path(path):
    if not path:
        raise LogicError("Path must be non-empty")
    if path[0] == "/":
        raise LogicError("Path must be relative")
