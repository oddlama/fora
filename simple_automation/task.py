"""
Provides the Task class.
"""

import os
import time
from pathlib import PurePosixPath

from simple_automation.checks import check_valid_path, check_valid_relative_path
from simple_automation.exceptions import LogicError
from simple_automation.transactions import git
from simple_automation.transactions.utils import template_str, resolve_mode_owner_group
from simple_automation.utils import ellipsis

class Task:
    """
    A base class for tasks. A task executes on a host context and runs a set
    of transactions on this context.

    Examples
    --------

    Every tasks needs an identifier and a description. The identifier can be used as a
    namespace for related variables.

    .. highlight:: python
    .. code-block:: python

        from simple_automation import Task

        class TaskZshConfig(Task):
            identifier = "zsh"
            description = "Installs a global zsh configuration"

            def run(self, context):
                with context.defaults(umask=0o022, dir_mode=0o755, file_mode=0o644):
                    # Copy configuration
                    directory(context, path="/etc/zsh")
                    template(context, src="templates/zsh/zshrc.j2", dst="/etc/zsh/zshrc")
                    template(context, src="templates/zsh/zprofile.j2", dst="/etc/zsh/zprofile")
    """

    identifier = None
    """
    The identifier of this task.
    """

    description = None
    """
    A short description of what the task does.
    """

    def __init__(self, manager):
        self.manager = manager

        if self.identifier is None:
            raise LogicError("A task must override the static variable 'identifier'")
        if self.description is None:
            raise LogicError("A task must override the static variable 'description'")

        # Initialize variable defaults
        self.var_enabled = f"tasks.{self.identifier}.enabled"
        self.manager.set(self.var_enabled, True)
        self.set_defaults()

    def set_defaults(self):
        """
        Optional callback for subclasses. Called when the task may define its global defaults.
        Default variable keys should be named like "tasks.{self.identifier}.variable_name".

        Examples
        --------

        Define variables so your task can be customized easily for your different systems.

        .. highlight:: python
        .. code-block:: python

            from simple_automation import Task

            class TaskZshConfig(Task):
                identifier = "zsh"
                description = "Installs a global zsh configuration"

                def set_defaults(self):
                    self.manager.set("tasks.zsh.config_folder", "/etc/zsh")

                def run(self, context):
                    # ...
                    template(context, src="templates/zsh/zshrc.j2", dst="{{ tasks.zsh.config_folder }}/zshrc")
        """
        # No-op by default

    def pre_run(self, context):
        """
        Called before self.run() is called. Prints the task's title by default.
        """
        # Print title and description
        title = f">>>> Task: {ellipsis(self.identifier, 24)} <<<<"
        if context.verbose >= 1:
            description = ellipsis(self.description, 80)
            print(f"\n[[33m*[m] [1;32m{title}[m [37m({description})[m")
        else:
            print(f"\n[[33m*[m] [1;32m{title}[m")

    def post_run(self, context):
        """
        Called after self.run() is called. No-op by default.
        """

    def enabled(self, context):
        """
        Returns true, if our enable variable is set to true in the given context.
        """
        return context.vars.get(self.var_enabled)

    def run(self, context):
        """
        To be overwritten by a subclass. Contain's the task's logic.
        """

    def exec(self, context):
        """
        Executes the actual task, as well as the pre and post functions
        in respective order, if the task is enabled for the current context.
        """
        if not self.enabled(context):
            return

        self.pre_run(context)
        # This should not be necessary, but as an added security measure,
        # we reset the context to it's initial defaults after executing the
        # pre_run function.
        context._set_defaults(user="root", umask=0o077, dir_mode=0o700, file_mode=0o600,
                              owner="root", group="root")
        self.run(context)
        self.post_run(context)

class TrackedTask(Task):
    """
    A base class for tasks which want to track changes in a git repository.
    All tracking will be done after :meth:`~run()` has finished.

    Examples
    --------

    Generally, to track files or directories, you have to inherit from :class:`TrackedTask <simple_automation.task.TrackedTask>`
    instead of :class:`Task <simple_automation.task.Task>`. It may be beneficial to
    create your own base class for all tracked tasks, to set a common tracking repository.
    You will then only have to add all files and directories you want to track to
    :attr:`~tracking_paths` in the actual task.

    .. highlight:: python
    .. code-block:: python

        from simple_automation import TrackedTask

        class MyTrackedTask(TrackedTask):
            tracking_repo_url = "{{ tracking.repo_url }}"
            tracking_local_dst = "/var/lib/root/tracking"

    To track a config file, simply extend your task with the correct tracking path:

    .. highlight:: python
    .. code-block:: python

        class TaskZshConfig(MyTrackedTask):
            tracking_paths = ["/etc/zsh"]
            # ...

    To track dynamic information, first save it to a file:

    .. highlight:: python
    .. code-block:: python

        # Track installed packages from portage
        class TaskTrackInstalledPackages(MyTrackedTask):
            identifier = "track_installed_packages"
            description = "Tracks all installed packages"
            tracking_paths = ["/var/lib/root/installed_packages"]

            def run(self, context):
                save_output(context, command=["qlist", "-CIv"],
                            dst="/var/lib/root/installed_packages",
                            desc="Query installed packages")
    """

    identifier = None
    """
    The identifier of this task.
    """

    description = None
    """
    A short description of what the task does.
    """

    tracking_repo_url = None
    """
    The remote url to the repository which will be used as the tracking repo.
    Will be templated by the currently executed context.
    For example:
    - (via ssh)   "git@github.com:myuser/tracked-system-settings"
    - (via https) "https://{{ personal_access_token }}@github.com/myuser/tracked-system-settings"
    Remember to put secrets into a vault so they aren't checked into your repository in plain text.
    We recommend using ssh, as secrets in the url will be printed to the terminal when executed.
    """

    tracking_local_dst = None # e.g. "/var/lib/root/system_settings"
    """
    The path where the local clone of the repository will be.
    Will be templated by the currently executed context.
    """

    tracking_subpath = "{{ context.host.identifier }}" # e.g. "desktops/mymachine"
    """
    The subpath in the repository where the tracked files will be held.
    Will be templated by the currently executed context.
    It defaults to the identifier of the machine.
    """

    tracking_user = "root"
    """
    The user to execute all tracking commands as, and the user which will own all related files.
    The rsync will always be called as root so it may access arbitrary paths.
    """

    tracking_group = "root"
    """
    The group which will own tracking related files.
    """

    tracking_paths = []
    """
    A list of directories and/or files that should be tracked.
    Will be templated by the currently executed context.
    """

    tracking_repo_configs = {
        "user.name": "{{ context.host.identifier }}",
        "user.email": "root@localhost" }
    """
    A dictionary of git configs to be set locally when the repository is first created.
    Values will be templated by the currently executed context.

    By default, it sets user.name to the host identifier, and user.email to root@localhost.
    (for each entry, 'git config --local {key} {value}' is executed). Useful to set
    name and email, and maybe a gpg signing key.
    """

    tracking_git_commit_opts = []
    """
    Extra options to 'git commit'.
    Will be templated by the currently executed context.
    """


    class TaskInitializeTracking(Task):
        """
        A sub-task used to initialize the tracking repository.

        We remember the tracked
        parent task, so so we have access to the tracking specific variables later.
        """
        identifier = "initialize_tracking"
        description = "Initialize the tracking repository"

        def __init__(self, tracked_task):
            super().__init__(tracked_task.manager)
            self.tracked_task = tracked_task

        def enabled(self, context):
            return True

        def run(self, context):
            # Get tracking specific variables
            (url, dst, _) = context.cache["tracking"][self.tracked_task.tracking_id]

            # Clone or update remote tracking repository
            git.checkout(context, url, dst)

            if not context.pretend:
                # Set given git repo configs
                for k,v in self.tracked_task.tracking_repo_configs.items():
                    v = template_str(context, v)
                    context.remote_exec(["git", "-C", dst, "config", "--local", k, v], checked=True)


    def __init__(self, manager):
        super().__init__(manager)
        if self.tracking_repo_url is None:
            raise LogicError("A tracked task must override the variable 'tracking_repo_url'")
        if self.tracking_local_dst is None:
            raise LogicError("A tracked task must override the variable 'tracking_local_dst'")
        if self.tracking_paths == []:
            raise LogicError("A tracked task must override the variable 'tracking_paths'")
        self.tracking_id = None

    def _resolve_variables(self, context):
        """
        Resolve the templated variables for this tracked task
        """
        url = template_str(context, self.tracking_repo_url)
        dst = template_str(context, self.tracking_local_dst)
        sub = template_str(context, self.tracking_subpath)
        tracking_id = f"{url}:{dst}/{sub}"
        check_valid_path(dst)
        check_valid_relative_path(sub)
        return (tracking_id, url, dst, sub)

    def pre_run(self, context):
        self._initialize_tracking(context)
        super().pre_run(context)
        self._assert_tracking_repo_clean(context)

    def post_run(self, context):
        super().post_run(context)
        self._track(context)

    def _initialize_tracking(self, context):
        if self.tracking_id is not None:
            return

        if "tracking" not in context.cache:
            # Create tracking cache
            context.cache["tracking"] = {}

        # Resolve templated variables
        (self.tracking_id, url, dst, sub) = self._resolve_variables(context)

        # Check if tracking has been initialized for this context
        if self.tracking_id not in context.cache["tracking"]:
            context.cache["tracking"][self.tracking_id] = (url, dst, sub)
            # Initialize now
            TrackedTask.TaskInitializeTracking(self).exec(context)

    def _assert_tracking_repo_clean(self, context):
        """
        Asserts that the tracking repository is clean, so we will never
        confuse different changes in a commit.
        """
        (_, dst, _) = context.cache["tracking"][self.tracking_id]

        if not context.pretend:
            # Assert that the repository is clean
            remote_status = context.remote_exec(["git", "-C", dst, "status", "--porcelain"], checked=True)
            if remote_status.stdout.strip() != "":
                raise LogicError("Refusing operation: Tracking repository is not clean!")

    def _track(self, context):
        """
        Uses rsync to copy the tracking paths into the repository, and
        creates and pushes a commit if there are any changes.
        """
        with context.defaults(user=self.tracking_user, owner=self.tracking_user, group=self.tracking_group):
            (_, dst, sub) = context.cache["tracking"][self.tracking_id]

            # Check source paths
            srcs = []
            for src in self.tracking_paths:
                src = template_str(context, src)
                check_valid_path(src)
                srcs.append(src)

            # Begin transaction
            with context.transaction(title="track", name=f"{srcs}") as action:
                action.initial_state(added=0, modified=0, deleted=0)

                if not context.pretend:
                    mode, owner, group = resolve_mode_owner_group(context, None, None, None, context.dir_mode)
                    rsync_dst = f"{dst}/{sub}/"
                    base_parts = PurePosixPath(dst).parts
                    parts = PurePosixPath(rsync_dst).parts

                    # Create tracking destination subdirectories if they don't exist
                    cur = dst
                    for p in parts[len(base_parts):]:
                        cur = os.path.join(cur, p)
                        context.remote_exec(["mkdir", "-p", "--", cur], checked=True)
                        context.remote_exec(["chown", f"{owner}:{group}", cur], checked=True)
                        context.remote_exec(["chmod", mode, cur], checked=True)

                    # Use rsync to backup all paths into the repository
                    for src in srcs:
                        context.remote_exec(["rsync", "--quiet", "--recursive", "--one-file-system",
                                             "--links", "--times", "--relative", str(PurePosixPath(src)), rsync_dst],
                                            checked=True, user="root", umask=0o022)

                    # Add all changes
                    context.remote_exec(["git", "-C", dst, "add", "--all"], checked=True)

                    # Query changes for message
                    remote_status = context.remote_exec(["git", "-C", dst, "status", "--porcelain"], checked=True)
                    if remote_status.stdout.strip() != "":
                        # We have changes
                        added = 0
                        modified = 0
                        deleted = 0
                        for line in remote_status.stdout.splitlines():
                            if line.startswith("A"):
                                added += 1
                            elif line.startswith("M"):
                                modified += 1
                            elif line.startswith("D"):
                                deleted += 1
                        action.final_state(added=added, modified=modified, deleted=deleted)

                        # Create commit
                        commit_opts = [template_str(context, o) for o in self.tracking_git_commit_opts]
                        context.remote_exec(["git", "-C", dst, "commit"] + commit_opts + ["--message", f"task {self.identifier}: {added=}, {modified=}, {deleted=}"], checked=True)

                        # Push commit
                        context.remote_exec(["git", "-C", dst, "push", "origin", "master"], checked=True)

                        action.success()
                    else:
                        # Repo is still clean
                        action.unchanged()
                else:
                    action.final_state(added="? (pretend)", modified="? (pretend)", deleted="? (pretend)")
                    action.success()
