"""
Provides some convenience checking functions that raise exceptions on errors.
"""
from simple_automation.exceptions import LogicError

def check_valid_key(key: str, msg: str = "Invalid key"):
    """
    Asserts that a given key is a valid identifier.

    Parameters
    ----------
    key : str
        The key to check.
    msg : str, optional
        The message to raise when the check fails.
    """
    if not key:
        raise LogicError("Invalid empty key")
    if '..' in key or not all([k.isidentifier() for k in key.split('.')]):
        raise LogicError(f"{msg}: '{key}' is not a valid identifier")

def check_valid_path(path):
    """
    Asserts that a given path is non empty and absolute.

    Parameters
    ----------
    path : str
        The path to check.
    """
    if not path:
        raise LogicError("Path must be non-empty")
    if path[0] != "/":
        raise LogicError("Path must be absolute")

def check_valid_relative_path(path):
    """
    Asserts that a given path is non empty and relative.

    Parameters
    ----------
    path : str
        The path to check.
    """
    if not path:
        raise LogicError("Path must be non-empty")
    if path[0] == "/":
        raise LogicError("Path must be relative")
