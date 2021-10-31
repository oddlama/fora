"""
Provides operations related to creating and modifying files and directories.
"""

import hashlib
from typing import Optional

import simple_automation
from simple_automation.operations.api import Operation, OperationResult, operation
from simple_automation.operations.utils import check_absolute_path

@operation("dir")
def directory(op: Operation,
              path: str,
              mode: Optional[str] = None,
              owner: Optional[str] = None,
              group: Optional[str] = None) -> OperationResult:
    """
    Manages the state of an directory on the remote host.
    If the path already exists but isn't a directory, the operation will fail.

    Parameters
    ----------
    op
        The operation wrapper. Must not be supplied by the user.
    path
        The directory path.
    mode
        The directory mode. Uses the remote execution defaults if None.
    owner
        The directory owner. Uses the remote execution defaults if None.
    group
        The directory group. Uses the remote execution defaults if None.
    """
    check_absolute_path(path)
    op.desc(path)

    with op.defaults(dir_mode=mode, owner=owner, group=group) as attr:
        op.final_state(exists=True, mode=attr.dir_mode, owner=attr.owner, group=attr.group)

        # Examine current state
        stat = op.connection().stat(path)
        if stat is None:
            # The directory doesn't exist
            op.initial_state(exists=False, mode=None, owner=None, group=None)
        else:
            if stat.type != "dir":
                raise ValueError(f"path '{path}' exists but is not a directory!")

            # The directory exists but may have different attributes
            op.initial_state(exists=True, mode=stat.mode, owner=stat.owner, group=stat.group)

        # Return success if nothing needs to be changed
        if op.unchanged():
            return op.success()

        # Apply actions to reach desired state, but only if we are not doing a dry run
        if not simple_automation.args.dry:
            # Create directory if it doesn't exist
            if op.changed("exists"):
                op.connection().run(["mkdir", "--", path])

            # Set correct mode, if needed
            if op.changed("mode"):
                op.connection().run(["chmod", attr.dir_mode, "--", path])

            # Set correct owner and group, if needed
            if op.changed("owner") or op.changed("group"):
                op.connection().run(["chown", f"{attr.owner}:{attr.group}", "--", path])

            # TODO: diff imporant things
            #if simple_automation.args.diff:

        return op.success()

@operation("save_content")
def save_content(op: Operation,
                 content: bytes,
                 dest: str,
                 mode: Optional[str] = None,
                 owner: Optional[str] = None,
                 group: Optional[str] = None) -> OperationResult:
    """
    Saves the given content as dest on the remote host.

    Parameters
    ----------
    op
        The operation wrapper. Must not be supplied by the user.
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
    check_absolute_path(dest)
    op.desc(dest)

    with op.defaults(file_mode=mode, owner=owner, group=group) as attr:
        final_sha512sum = hashlib.sha512(content).digest()
        op.final_state(exists=True, mode=attr.file_mode, owner=attr.owner, group=attr.group, sha512=final_sha512sum)

        # Examine current state
        stat = op.connection().stat(dest, sha512sum=True)
        if stat is None:
            # The directory doesn't exist
            op.initial_state(exists=False, mode=None, owner=None, group=None, sha512=None)
        else:
            if stat.type != "file":
                raise ValueError(f"path '{dest}' exists but is not a file!")

            # The file exists but may have different attributes or content
            op.initial_state(exists=True, mode=stat.mode, owner=stat.owner, group=stat.group, sha512=stat.sha512sum)

        # Return success if nothing needs to be changed
        if op.unchanged():
            return op.success()

        # Apply actions to reach desired state, but only if we are not doing a dry run
        if not simple_automation.args.dry:
            # Create directory if it doesn't exist
            if op.changed("exists") or op.changed("sha512"):
                op.connection().save_content(
                        file=dest,
                        content=content,
                        mode=attr.file_mode,
                        owner=attr.owner,
                        group=attr.group)
            else:
                # Set correct mode, if needed
                if op.changed("mode"):
                    op.connection().run(["chmod", attr.file_mode, "--", dest])

                # Set correct owner and group, if needed
                if op.changed("owner") or op.changed("group"):
                    op.connection().run(["chown", f"{attr.owner}:{attr.group}", "--", dest])

            # TODO: diff imporant things
            #if simple_automation.args.diff:

        return op.success()

@operation("upload")
def upload(op: Operation,
           src: str,
           dest: str,
           mode: Optional[str] = None,
           owner: Optional[str] = None,
           group: Optional[str] = None) -> OperationResult:
    """
    Uploads a local file or directory to the remote host.

    Parameters
    ----------
    op
        The operation wrapper. Must not be supplied by the user.
    src
        The file to upload.
    dest
        The remote destination path.
    mode
        The file mode. Uses the remote execution defaults if None.
    owner
        The file owner. Uses the remote execution defaults if None.
    group
        The file group. Uses the remote execution defaults if None.
    """
    with open(src, 'rb') as f:
        return save_content(op, f.read(), dest, mode, owner, group)

# TODO content
# TODO template
# TODO unix user, group, user_supplementary_group
# TODO allow nested operations? if yes, they should nest the logs
#      (maybe indent automatically at begin of each operation.
#      nesting could lead to possible problem/complication with state checking, dry run, etc.
