"""
Provides operations related to creating and modifying files and directories.
"""

from typing import Optional

import simple_automation
from simple_automation.operations.api import Operation, OperationResult, operation
from simple_automation.operations.utils import check_absolute_path

@operation("dir")
def directory(op: Operation,
              path: str,
              delete_existing: bool = False,
              mode: Optional[str] = None,
              owner: Optional[str] = None,
              group: Optional[str] = None) -> OperationResult:
    """
    Manages the state of an directory on the remote.

    Parameters
    ----------
    op
        The operation wrapper. Must not be supplied by the user.
    path
        The directory path.
    delete_existing
        Determines action if the path already exists but is not a directory.
        False will abort the operation with a failure, True will
        automatically delete and recreate the path as a directory.
    mode
        The directory mode. Uses the remote execution defaults if None.
    owner
        The directory owner. Uses the remote execution defaults if None.
    group
        The directory group. Uses the remote execution defaults if None.
    """
    check_absolute_path(path)

    with op.defaults(dir_mode=mode, owner=owner, group=group) as attr:
        op.final_state(exists=True, mode=attr.dir_mode, owner=attr.owner, group=attr.group)

        # Examine current state
        stat = op.connection().stat(path)
        if stat is None:
            # The directory doesn't exist
            op.initial_state(exists=False, mode=None, owner=None, group=None)
        else:
            if stat.type != "dir":
                if not delete_existing:
                    raise ValueError(f"path '{path}' exists but is not a directory!")

                # Something else exists but may have different attributes
                op.initial_state(exists=False, mode=None, owner=None, group=None)
            else:
                # The directory exists but may have different attributes
                op.initial_state(exists=True, mode=stat.mode, owner=stat.owner, group=stat.group)

        # Return success if nothing needs to be changed
        if op.unchanged():
            return op.success()

        # Apply actions to reach desired state, but only if we are not doing a dry run
        if not simple_automation.args.dry:
            # Replace existing path if desired
            if delete_existing and stat is not None and stat.type != "dir":
                op.connection().run(["rm", "-rf", path], check=True)

            # Create directory if it doesn't exist
            if op.changed("exists"):
                op.connection().run(["mkdir", path], check=True)

            # Set correct mode, if needed
            if op.changed("mode"):
                op.connection().run(["chmod", attr.dir_mode, path], check=True)

            # Set correct owner and group, if needed
            if op.changed("owner") or op.changed("group"):
                op.connection().run(["chown", f"{attr.owner}:{attr.group}", path], check=True)

            # TODO: diff imporant things
            #if simple_automation.args.diff:

        return op.success()
