from simple_automation.utils import ellipsis

class Task:
    def __init__(self, manager):
        self.manager = manager
        # Initialize variable defaults
        self.set_defaults(manager)

    def exec(self, context):
        # Print title
        title = f">>>> Task: {ellipsis(self.identifier, 24)} <<<<"
        description = ellipsis(self.description, 80)
        print(f"[[33m*[m] [1m{title}[m [37m({description})[m")

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
