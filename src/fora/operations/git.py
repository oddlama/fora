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
         branch: str = None,
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
    TODO

    Parameters
    ----------
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
    op.desc(f"{url} {path}")

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
    remote_newest_commit = conn.run(["git", "ls-remote", "--exit-code", "--", url, "HEAD"])
    newest_commit = (remote_newest_commit.stdout or b"").decode("utf-8", errors="backslashreplace").strip().split()[0]

    op.final_state(initialized=True, commit=newest_commit)

    # Return success if nothing needs to be changed
    if op.unchanged():
        return op.success()

    # Apply actions to reach new state, if we aren't in pretend mode
    if not G.args.dry:
        if stat_path is None:
            # Create a fresh clone of the repository
            cmd = ["git", "clone"]
            if depth is not None:
                cmd.extend(["--depth", str(depth)])
            cmd.extend(["--", url, path])

            conn.run(cmd)
        elif update:
            # Update the existing repository
            # TODO: assert that the remote url matches! not that we pull an unrelated repo...
            cmd = ["git", "-C", path, "pull"]
            if depth is not None:
                cmd.extend(["--depth", str(depth)])

            conn.run(cmd)

    return op.success()
