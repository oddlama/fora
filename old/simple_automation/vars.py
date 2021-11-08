"""
Provides the Vars class.
"""

from simple_automation.checks import check_valid_key
from simple_automation.exceptions import LogicError

class Vars:
    """
    The Vars class represents a nested dictionary, that allows setting
    variables in children dicts by using '.' in the key as a delimiter.
    """

    def __init__(self):
        """
        Initializes with an empty dictionary.
        """
        self.vars = {}
        self.warn_on_redefinition = False

    def copy(self, key, other_vars):
        """
        Copies a value from another vars object into this one.
        Same as calling self.set(key, other_vars.get(key))

        Parameters
        ----------
        key : str
            The key that should be copied.
        other_vars : Vars
            The source variable storage where the key is copied from.
        """
        self.set(key, other_vars.get(key))

    def get(self, key, default=None):
        """
        Retrieves a variable by the given key. If no such key exists,
        it returns the given default value or throws a KeyError if no default is set.

        Parameters
        ----------
        key : str
            The key that should be read.
        default : Any, optional
            If not None, this will be returned in case the key is unset. By default None.

        Returns
        -------
        Any
            The stored object.
        """

        def get_or_throw(key):
            """
            Retrieves a variable by the given key or raises a KeyError if no such key exists.
            """
            check_valid_key(key)
            d = self.vars
            cs = []
            for k in key.split('.'):
                cs.append(k)
                if not isinstance(d, dict):
                    csname = '.'.join(cs)
                    raise LogicError(f"Cannot access variable '{key}' because '{csname}' is not a dictionary")

                if k not in d:
                    raise KeyError(f"Variable '{key}' does not exist")
                d = d[k]
            return d

        if default is None:
            return get_or_throw(key)

        try:
            return get_or_throw(key)
        except KeyError:
            return default

    def set(self, key, value):
        """
        Sets the given variable.

        Parameters
        ----------
        key : str
            The key that should be read.
        value : Any, optional
            The value to be stored. Must be json (de-)serializable.
        """
        check_valid_key(key)
        d = self.vars
        cs = []
        keys = key.split('.')
        for k in keys[:-1]:
            if k not in d:
                d[k] = {}
            d = d[k]

            cs.append(k)
            if not isinstance(d, dict):
                csname = '.'.join(cs)
                raise LogicError(f"Cannot set variable '{key}' because existing variable '{csname}' is not a dictionary")

        if self.warn_on_redefinition and keys[-1] in d:
            print(f"[1;33mwarning:[m [1mRedefinition of variable '{key}':[m previous={d[keys[-1]]} new={value}")

        d[keys[-1]] = value
