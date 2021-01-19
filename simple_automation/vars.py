from simple_automation import LogicError
from simple_automation.checks import check_valid_key

class Vars:
    def __init__(self):
        self.vals = {}

    def get(self, key):
        check_valid_key(key)
        d = self.vals
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

    def get(self, key, default):
        try:
            return self.get(key)
        except KeyError:
            return default

    def set(self, key, value):
        check_valid_key(key)
        d = self.vals
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
