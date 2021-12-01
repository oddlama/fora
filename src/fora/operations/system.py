"""Provides operations related to the operating system such as user, group or service management."""

from typing import Optional

import fora.host
from fora.operations.api import Operation, OperationResult, operation

@operation("user")
def user(user: str,
         present: bool = True,
         group: Optional[str] = None,
         groups: Optional[list[str]] = None,
         append_groups: bool = False,
         system: bool = False,
         shell: Optional[str] = None,
         password_hash: Optional[str] = None,
         home: Optional[str] = None,
         create_home: bool = True,
         comment: Optional[str] = None,
         name: Optional[str] = None,
         check: bool = True,
         op: Operation = Operation.internal_use_only) -> OperationResult:
    """
    .

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
    # pylint: disable=too-many-branches
    _ = (name, check) # Processed automatically.
    op.desc(user)
    conn = fora.host.current_host.connection

    # Query current state



    if present:
        op.final_state(exists=True, group=, groups=, system=, shell=, password_hash=, home=, comment=)
    else:
        op.final_state(exists=False, mode=None, owner=None, group=None, touched=False)

    # Examine current state
    stat = conn.stat(path)
    if stat is None:
        # The directory doesn't exist
        op.initial_state(exists=False, mode=None, owner=None, group=None, touched=False)
    else:
        if stat.type != "dir":
            raise OperationError(f"path '{path}' exists but is not a directory!")

        # The directory exists but may have different attributes
        op.initial_state(exists=True, mode=stat.mode, owner=stat.owner, group=stat.group, touched=False)

    # Return success if nothing needs to be changed
    if op.unchanged():
        return op.success()

    # Apply actions to reach desired state, but only if we are not doing a dry run
    if not G.args.dry:
        if present:
            # Create directory if it doesn't exist
            if op.changed("exists"):
                conn.run(["mkdir", "--", path])

            # Set correct mode, if needed
            if op.changed("mode"):
                conn.run(["chmod", attr.dir_mode, "--", path])

            # Set correct owner and group, if needed
            if op.changed("owner") or op.changed("group"):
                conn.run(["chown", f"{attr.owner}:{attr.group}", "--", path])

            # Touch directory if requested
            if not op.changed("exists") and op.changed("touched"):
                conn.run(["touch", "--", path])
        else:
            # Remove directory if it should not be present
            if op.changed("exists"):
                conn.run(["rm", "-rf", "--", path])

    return op.success()
