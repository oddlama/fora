class Context:
    def __init__(self):
        self.dir_mode = 0o700
        self.file_mode = 0o600
        self.owner = "root"
        self.group = "root"
        self.umask_value = 0o077

    def defaults(self, dir_mode, file_mode, owner, group):
        self.dir_mode = dir_mode
        self.file_mode = file_mode
        self.owner = owner
        self.group = group

    def umask(self, value):
        self.umask_value = value
