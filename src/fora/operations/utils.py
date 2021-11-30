"""
Provides utiliy functions for operations.
"""

import hashlib
from typing import Optional, Union
import fora.host

from fora import globals as G
from fora.operations.api import Operation, OperationError, OperationResult

def save_content(op: Operation,
                 content: Union[bytes, str],
                 dest: str,
                 mode: Optional[str] = None,
                 owner: Optional[str] = None,
                 group: Optional[str] = None) -> OperationResult:
    """
    Saves the given content as dest on the remote host. Only for use within an operation,
    if save_content is the main functionality. You must supply the op parameter.

    Parameters
    ----------
    op
        The operation wrapper.
    content
        The file content.
    dest
        The remote destination path.
    mode
        The file mode. Uses the remote execution defaults if None.
    owner
        The file owner. Uses the remote execution defaults if None.
    group
        The file group. Uses the remote execution defaults if None.
    """
    if isinstance(content, str):
        content = content.encode('utf-8')

    conn = fora.host.current_host.connection
    with op.defaults(file_mode=mode, owner=owner, group=group) as attr:
        final_sha512sum = hashlib.sha512(content).digest()
        op.final_state(exists=True, mode=attr.file_mode, owner=attr.owner, group=attr.group, sha512=final_sha512sum)

        # Examine current state
        stat = conn.stat(dest, sha512sum=True)
        if stat is None:
            # The directory doesn't exist
            op.initial_state(exists=False, mode=None, owner=None, group=None, sha512=None)
        else:
            if stat.type != "file":
                raise OperationError(f"path '{dest}' exists but is not a file!")

            # The file exists but may have different attributes or content
            op.initial_state(exists=True, mode=stat.mode, owner=stat.owner, group=stat.group, sha512=stat.sha512sum)

        # Return success if nothing needs to be changed
        if op.unchanged():
            return op.success()

        # Add diff if desired
        if G.args.diff:
            op.diff(dest, conn.download_or(dest), content)

        # Apply actions to reach desired state, but only if we are not doing a dry run
        if not G.args.dry:
            # Create directory if it doesn't exist
            if op.changed("exists") or op.changed("sha512"):
                conn.upload(
                        file=dest,
                        content=content,
                        mode=attr.file_mode,
                        owner=attr.owner,
                        group=attr.group)
            else:
                # Set correct mode, if needed
                if op.changed("mode"):
                    conn.run(["chmod", attr.file_mode, "--", dest])

                # Set correct owner and group, if needed
                if op.changed("owner") or op.changed("group"):
                    conn.run(["chown", f"{attr.owner}:{attr.group}", "--", dest])

        return op.success()

def check_absolute_path(path: str) -> None:
    """
    Asserts that a given path is non empty and absolute.

    Parameters
    ----------
    path
        The path to check.
    """
    if not path:
        raise ValueError("path must be non-empty")
    if path[0] != "/":
        raise ValueError("path must be absolute")
