from simple_automation.utils import ellipsis
from simple_automation.checks import check_valid_path, check_valid_relative_path
from simple_automation.transactions.basic import _template_str, _remote_stat
from simple_automation.transactions import git

class Task:
    """
    A base class for tasks. A task executes on a host context and runs a set
    of transactions on this context.
    """
    def __init__(self, manager):
        self.manager = manager
        # Initialize variable defaults
        self.set_defaults(manager)

    def set_defaults(self, manager):
        # No-op by default
        pass

    def pre_run(self, context):
        """
        Called before self.run() is called.
        """
        # Print title
        title = f">>>> Task: {ellipsis(self.identifier, 24)} <<<<"
        description = ellipsis(self.description, 80)
        print(f"[[33m*[m] [1m{title}[m [37m({description})[m")

    def post_run(self, context):
        """
        Called after self.run() is called.
        """
        pass

    def exec(self, context):
        """
        Executes the actual task, as well as the pre and post functions in respective order.
        """
        self.pre_run(context)
        # Set safe context defaults
        context.defaults(user="root", umask=0o077, dir_mode=0o700, file_mode=0o600,
                         owner="root", group="root")
        self.run(context)
        self.post_run(context)

class TrackedTask(Task):
    """
    A base class for tasks which want to track changes in a git repository.
    """

    """
    The remote url to the repository which will be used as the tracking repo.
    Will be templated by the currently executed context.
    """
    tracking_repo_url = None # e.g. "git@github.com:{}/system_settings",

    """
    The path where the local clone of the repository will be.
    Will be templated by the currently executed context.
    """
    tracking_local_dst = None # e.g. "/var/lib/root/system_settings"

    """
    The subpath in the repository where the tracked files will be held.
    Will be templated by the currently executed context.
    It defaults to the identifier of the machine.
    """
    tracking_subpath = "{{ context.host.identifier }}" # e.g. "desktops/mymachine"

    class TaskInitializeTracking(Task):
        """
        A sub-task used to initialize the tracking repository.
        """
        identifier = "tracking"
        description = "Initialize the tracking repository"

        def __init__(self, tracking_id):
            """
            Initialize this tracking initialization task and remember the tracking
            id, so so we have access to the tracking specific variables later.
            """
            self.tracking_id = tracking_id

        def run(self, context):
            # Set defaults
            context.defaults(user="root", umask=0o077, dir_mode=0o700, file_mode=0o600,
                             owner="root", group="root")

            # Get tracking specific variables
            (url, dst, sub) = context.cache["tracking"][self.tracking_id]

            # Clone or update remote tracking repository
            git.checkout(context, url, dst)


    def _resolve_variables(self, context):
        """
        Resolve the templated variables for this tracked task
        """
        url = _template_str(context, self.tracking_repo_url)
        dst = _template_str(context, self.tracking_local_dst)
        sub = _template_str(context, self.tracking_subpath)
        tracking_id = f"{url}:{dst}/{sub}"
        check_valid_path(dst)
        check_valid_relative_path(sub)
        return (tracking_id, url, dst, sub)

    def __init__(self, manager):
        super().__init__(manager)
        if self.tracking_repo_url is None:
            raise LogicError("A tracked task must override the variable 'tracking_repo_url'")
        if self.tracking_local_dst is None:
            raise LogicError("A tracked task must override the variable 'tracking_local_dst'")

    def pre_run(self, context):
        self._initialize_tracking(context)
        super().pre_run(context)
        self._assert_tracking_repo_clean(context)

    def post_run(self, context):
        super().post_run(context)

    def _initialize_tracking(self, context):
        if "tracking" not in context.cache:
            # Create tracking cache
            context.cache["tracking"] = {}

        # Resolve templated variables
        (tid, url, dst, sub) = self._resolve_variables(context)

        # Check if tracking has been initialized for this context
        if tid not in context.cache["tracking"]:
            context.cache["tracking"][tid] = (url, dst, sub)
            # Initialize now
            TaskInitializeTracking(self).exec(context)

    def _assert_tracking_repo_clean(self, context):
        dst = context.cache["tracking"]["dst"]

        # Assert that the repository is clean
        remote_status = context.remote_exec(["git", "-C", dst, "status", "--porcelain"])
        if remote_status.return_code != 0:
            raise LogicError("Cannot query git repository status on remote: Command 'git status --porcelain' failed")

        if remote_status.stdout.strip() != "":
            raise LogicError("Refusing operation: Tracking repository is not clean!")

    def _track(self, context):
        # TODO as a transaction pls for logging and shit
        # TODO: rsync all tracked paths to the tracking version control directory
        self._rsync_tracked_paths(context)
        # TODO: if anything changed make a commit based on the task's name
        # TODO: git add all self.tracked in destination
        # TODO: if there are changes, commit.
