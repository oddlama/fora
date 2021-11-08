"""
Provides utiliy functions for operations.
"""

from typing import Union

def check_absolute_path(path: str):
    """
    Asserts that a given path is non empty and absolute.

    Parameters
    ----------
    path
        The path to check.
    """
    if not path:
        raise ValueError("Path must be non-empty")
    if path[0] != "/":
        raise ValueError("Path must be absolute")

def modes_equal(a: Union[str, int], b: Union[str, int]) -> bool:
    """
    Checks if two unix-modes are equal. strs are interpreted as octal represenations.

    Parameters
    ----------
    a
        The first mode
    b
        The second mode

    Returns
    -------
    bool
        True if the modes are equal, False otherwise
    """
    if isinstance(a, str):
        a = int(a, 8)
    if isinstance(b, str):
        b = int(b, 8)
    return a == b
