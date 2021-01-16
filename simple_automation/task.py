class Task:
    def __init__(self, context):
        # Set default variables
        self.set_defaults(context)

    def exec(self, context):
        self.run(context)
        self._checkin_tracked_paths(context)

    def _checkin_tracked_paths(self, context):
        # TODO: rsync all tracked paths to the tracking version control directory
        self._rsync_tracked_paths(context)
        # TODO: if anything changed make a commit based on the task's name
        # TODO: git add all self.tracked in destination
        # TODO: if there are changes, commit.

    def _rsync_tracked_paths(self, context):
        pass
