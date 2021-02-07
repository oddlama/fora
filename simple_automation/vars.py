from simple_automation import LogicError
from simple_automation.checks import check_valid_key

class Vars:
    def __init__(self):
        self.vars = {}
        self.warn_on_redefinition = False

    def get(self, key, default=None):
        """
        Retrieves a variable by the given key. If no such key exists,
        it returns the given default value or throws a KeyError if no default is set.
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
                else:
                    d = d[k]
            return d

        if default is None:
            return get_or_throw(key)
        else:
            try:
                return get_or_throw(key)
            except KeyError:
                return default

    def set(self, key, value):
        """
        Sets the given variable.
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
