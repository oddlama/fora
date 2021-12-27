"""Provides operations related to git."""

import os
from typing import Optional
import fora.host
from fora import globals as G
from fora.operations.api import Operation, OperationResult, operation
from fora.operations.utils import check_absolute_path

@operation("repo")
def repo(url: str,
         path: str,
         branch_or_tag: Optional[str] = None,
         update: bool = True,
         depth: Optional[int] = None,
         rebase: bool = True,
         ff_only: bool = False,
         update_submodules: bool = False,
         recursive_submodules: bool = False,
         shallow_submodules: bool = False,
         name: Optional[str] = None,
         check: bool = True,
         op: Operation = Operation.internal_use_only) -> OperationResult:
    """
    Clones or updates a git repository and its submodules.

    Parameters
    ----------
    url
        The url to the git repository.
    path
        The path where the repository should be cloned.
    branch_or_tag
        Either a branch name or a tag to clone. Follows the default branch of the remote if not given.
    update
        Whether to keep the repository up to date if it has already been cloned.
    depth
        Keep the repository as a shallow clone with the specified number of commits.
        Also applies when pulling updates.
    rebase
        Use `--rebase` when pulling updates.
    ff_only
        Use `--ff-only` when pulling updates.
    update_submodules
        Also initialize and update submodules after cloning or pulling.
    recursive_submodules
        Recursively update submodules after cloning or pulling.
    shallow_submodules
        Also apply the given `depth` to submodule updates.
    name
        The name for the operation.
    check
        If True, returning `op.failure()` will raise an OperationError. All manually raised
        OperationErrors will be propagated. When False, any manually raised OperationError will
        be caught and `op.failure()` will be returned with the given message while continuing execution.
    op
        The operation wrapper. Must not be supplied by the user.
    """
    _ = (name, check) # Processed automatically.
    check_absolute_path(path)
    op.desc(f"{path} [{url}]")

    conn = fora.host.current_host.connection

    stat_path = conn.stat(path)
    if stat_path is None:
        op.initial_state(initialized=False, commit=None)
        cur_commit = None
    elif stat_path.type == "dir":
        # Assert that it is a git directory
        stat_git = conn.stat(os.path.join(path, ".git"))
        if stat_git is None:
            return op.failure(f"directory '{path}' already exists but is not a git repository")

        if stat_git.type != "dir":
            return op.failure(f"directory '{path}' already exists but doesn't contains a valid .git directory")

        remote_commit = conn.run(["git", "-C", path, "rev-parse", "HEAD"])
        cur_commit = (remote_commit.stdout or b"").decode("utf-8", errors="backslashreplace").strip()
        op.initial_state(initialized=True, commit=cur_commit)
    else:
        return op.failure(f"path '{path}' exists but is not a directory!")

    # If the repository is already cloned but we shouldn't update,
    # nothing will change and we are done.
    if stat_path is not None and not update:
        op.final_state(initialized=True, commit=cur_commit)
        return op.success()

    # Check the newest available commit
    remote_newest_commit = conn.run(["git", "ls-remote", "--exit-code", "--", url, branch_or_tag or "HEAD"])
    newest_commit = (remote_newest_commit.stdout or b"").decode("utf-8", errors="backslashreplace").strip().split()[0]

    op.final_state(initialized=True, commit=newest_commit)

    # Return success if nothing needs to be changed
    if op.unchanged():
        return op.success()

    # Apply actions to reach new state, if we aren't in pretend mode
    if not G.args.dry:
        if stat_path is None:
            # Create a fresh clone of the repository
            clone_cmd = ["git", "clone"]
            if depth is not None:
                clone_cmd.extend(["--depth", str(depth)])
            if branch_or_tag is not None:
                clone_cmd.extend(["--branch", branch_or_tag])
            clone_cmd.extend(["--", url, path])
            conn.run(clone_cmd)

            if update_submodules:
                # Initialize submodules if requested
                submodule_cmd = ["git", "-C", path, "submodule", "update", "--init"]
                if shallow_submodules and depth is not None:
                    submodule_cmd.extend(["--depth", str(depth)])
                if recursive_submodules:
                    submodule_cmd.extend(["--recursive"])
                conn.run(submodule_cmd)
        elif update:
            # Assert that the existing repository's remote url matches the given url to prevent pulling an unrelated repo
            ret_current_remote = conn.run(["git", "-C", path, "config", "--get", "remote.origin.url"])
            current_remote = (ret_current_remote.stdout or b"").decode("utf-8", errors="backslashreplace").strip()
            if current_remote != url:
                return op.failure(f"refusing to update existing git repository with different remote url '{current_remote}'")

            # Update the existing repository
            update_cmd = ["git", "-C", path, "pull"]
            if depth is not None:
                update_cmd.extend(["--depth", str(depth)])
            if rebase:
                update_cmd.append("--rebase")
            if ff_only:
                update_cmd.append("--ff-only")
            conn.run(update_cmd)

            if update_submodules:
                # Update submodules if requested
                submodule_update_cmd = ["git", "-C", path, "submodule", "update", "--init"]
                if shallow_submodules and depth is not None:
                    submodule_update_cmd.extend(["--depth", str(depth)])
                if recursive_submodules:
                    submodule_update_cmd.extend(["--recursive"])
                conn.run(submodule_update_cmd)

    return op.success()
