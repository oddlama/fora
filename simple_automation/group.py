from simple_automation.vars import Vars

class Group(Vars):
    def __init__(self, manager, identifier):
        super().__init__()
        self.manager = manager
        self.identifier = identifier
