import argparse

class Manager:
    def __init__(self):
        self.groups = {}
        self.hosts = {}
        self.tasks = {}
        self.vars = {}

    def add_group(self, identifier):
        group = Group(self, identifier)
        if identifier in self.groups:
            raise Exception(f"Cannot register group: Duplicate identifier {identifier}")
        self.groups[identifier] = group
        return group

    def add_host(self, identifier, ssh_host):
        host = Host(self, identifier, ssh_host)
        if identifier in self.hosts:
            raise Exception(f"Cannot register host: Duplicate identifier {identifier}")
        self.hosts[identifier] = host
        return host

    def add_task(self, task_ctor):
        task = task_ctor(self)
        if identifier in self.tasks:
            raise Exception(f"Cannot register task: Duplicate identifier {identifier}")
        self.tasks[identifier] = task
        return task

    def get(self, var):
        return self.vars[var]

    def set(self, var, val):
        self.vars[var] = val

    def main(self, run):
        run(Context())
