"""
Provides operations related to creating and modifying files and directories.
"""

import hashlib
import os
from os.path import join, relpath, normpath
from typing import Optional, Union, cast

from jinja2.exceptions import TemplateNotFound, UndefinedError

import simple_automation
from simple_automation import logger
from simple_automation.operations.api import Operation, OperationError, OperationResult, operation
from simple_automation.operations.utils import check_absolute_path

@operation("dir")
def directory(path: str,
              present: bool = True,
              touch: bool = False,
              mode: Optional[str] = None,
              owner: Optional[str] = None,
              group: Optional[str] = None,
              name: Optional[str] = None,
              op: Operation = Operation.internal_use_only) -> OperationResult:
    """
    Manages the state of an directory on the remote host.
    If the path already exists but isn't a directory, the operation will fail.

    Parameters
    ----------
    path
        The directory path.
    present
        Whether the directory should exist. If False, an existing directory (and its contents) will be deleted.
        If the path exists, but isn't a directory (but a file, link, ...) the operation will fail.
    touch
        Whether the directory should be touched (access and modification times will be updated).
    mode
        The directory mode. Uses the remote execution defaults if None.
    owner
        The directory owner. Uses the remote execution defaults if None.
    group
        The directory group. Uses the remote execution defaults if None.
    name
        The name for the operation.
    op
        The operation wrapper. Must not be supplied by the user.
    """
    _ = (name) # Processed automatically.
    check_absolute_path(path)
    op.desc(path)

    conn = simple_automation.host.connection
    with op.defaults(dir_mode=mode, owner=owner, group=group) as attr:
        op.final_state(exists=present, mode=attr.dir_mode, owner=attr.owner, group=attr.group, touched=touch)

        # Examine current state
        stat = conn.stat(path)
        if stat is None:
            # The directory doesn't exist
            op.initial_state(exists=False, mode=None, owner=None, group=None, touched=False)
        else:
            if stat.type != "dir":
                raise OperationError(f"path '{path}' exists but is not a link!")

            # The directory exists but may have different attributes
            op.initial_state(exists=True, mode=stat.mode, owner=stat.owner, group=stat.group, touched=False)

        # Return success if nothing needs to be changed
        if op.unchanged():
            return op.success()

        # Apply actions to reach desired state, but only if we are not doing a dry run
        if not simple_automation.args.dry:
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

@operation("file")
def file(path: str,
         present: bool = True,
         touch: bool = False,
         mode: Optional[str] = None,
         owner: Optional[str] = None,
         group: Optional[str] = None,
         name: Optional[str] = None,
         op: Operation = Operation.internal_use_only) -> OperationResult:
    """
    Creates, deletes or updates the given file.

    Parameters
    ----------
    path
        The remote file path.
    present
        Whether the file should exist. If False, an existing file will be deleted.
        If the path exists, but isn't a file (but a directory, link, ...) the operation will fail.
    touch
        Whether the file should be touched (access and modification times will be updated).
    mode
        The file mode. Uses the remote execution defaults if None.
    owner
        The file owner. Uses the remote execution defaults if None.
    group
        The file group. Uses the remote execution defaults if None.
    name
        The name for the operation.
    op
        The operation wrapper. Must not be supplied by the user.
    """
    _ = (name) # Processed automatically.
    check_absolute_path(path)
    op.desc(path)

    conn = simple_automation.host.connection
    with op.defaults(file_mode=mode, owner=owner, group=group) as attr:
        op.final_state(exists=present, mode=attr.file_mode, owner=attr.owner, group=attr.group, touched=touch)

        # Examine current state
        stat = conn.stat(path)
        if stat is None:
            # The file doesn't exist
            op.initial_state(exists=False, mode=None, owner=None, group=None, touched=False)
        else:
            if stat.type != "file":
                raise OperationError(f"path '{path}' exists but is not a file!")

            # The file exists but may have different attributes
            op.initial_state(exists=True, mode=stat.mode, owner=stat.owner, group=stat.group, touched=False)

        # Return success if nothing needs to be changed
        if op.unchanged():
            return op.success()

        # Apply actions to reach desired state, but only if we are not doing a dry run
        if not simple_automation.args.dry:
            if present:
                # Create file if it doesn't exist
                if op.changed("exists"):
                    conn.run(["touch", "--", path])

                # Set correct mode, if needed
                if op.changed("mode"):
                    conn.run(["chmod", attr.file_mode, "--", path])

                # Set correct owner and group, if needed
                if op.changed("owner") or op.changed("group"):
                    conn.run(["chown", f"{attr.owner}:{attr.group}", "--", path])

                # Touch file if requested
                if not op.changed("exists") and op.changed("touched"):
                    conn.run(["touch", "--", path])
            else:
                # Remove file if it should not be present
                if op.changed("exists"):
                    conn.run(["rm", "--", path])

        return op.success()

@operation("link")
def link(path: str,
         target: str,
         present: bool = True,
         touch: bool = False,
         owner: Optional[str] = None,
         group: Optional[str] = None,
         name: Optional[str] = None,
         op: Operation = Operation.internal_use_only) -> OperationResult:
    """
    Creates, deletes or updates the given symbolic link.

    Parameters
    ----------
    path
        The path of the link.
    target
        The target path which the link points to.
    present
        Whether the link should exist. If False, an existing link will be deleted.
        If the path exists, but isn't a link (but a directory, file, ...) the operation will fail.
    touch
        Whether the link should be touched (access and modification times will be updated). This affects the link itself, not the content!
    owner
        The link owner. Uses the remote execution defaults if None.
    group
        The link group. Uses the remote execution defaults if None.
    name
        The name for the operation.
    op
        The operation wrapper. Must not be supplied by the user.
    """
    _ = (name) # Processed automatically.
    check_absolute_path(path)
    op.desc(path)

    conn = simple_automation.host.connection
    with op.defaults(owner=owner, group=group) as attr:
        op.final_state(exists=present, owner=attr.owner, group=attr.group, touched=touch)

        # Examine current state
        stat = conn.stat(path)
        if stat is None:
            # The link doesn't exist
            op.initial_state(exists=False, owner=None, group=None, touched=False)
        else:
            if stat.type != "link":
                raise OperationError(f"path '{path}' exists but is not a link!")

            # The link exists but may have different attributes
            op.initial_state(exists=True, owner=stat.owner, group=stat.group, touched=False)

        # Return success if nothing needs to be changed
        if op.unchanged():
            return op.success()

        # Apply actions to reach desired state, but only if we are not doing a dry run
        if not simple_automation.args.dry:
            if present:
                # Create link if it doesn't exist
                if op.changed("exists"):
                    conn.run(["ln", "-s", "--", target, path])

                # Set correct owner and group, if needed
                if op.changed("owner") or op.changed("group"):
                    conn.run(["chown", "--no-dereference", f"{attr.owner}:{attr.group}", "--", path])

                # Touch link if requested
                if not op.changed("exists") and op.changed("touched"):
                    conn.run(["touch", "--no-dereference", "--", path])
            else:
                # Remove file if it should not be present
                if op.changed("exists"):
                    conn.run(["rm", "--", path])

        return op.success()

def _save_content(content: Union[bytes, str],
                  dest: str,
                  mode: Optional[str] = None,
                  owner: Optional[str] = None,
                  group: Optional[str] = None,
                  op: Operation = Operation.internal_use_only) -> OperationResult:
    """
    Saves the given content as dest on the remote host.

    Parameters
    ----------
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
    op
        The operation wrapper. Must not be supplied by the user.
    """
    check_absolute_path(dest)
    op.desc(dest)

    if isinstance(content, str):
        content = content.encode('utf-8')

    conn = simple_automation.host.connection
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

        # Apply actions to reach desired state, but only if we are not doing a dry run
        if not simple_automation.args.dry:
            # Create directory if it doesn't exist
            if op.changed("exists") or op.changed("sha512"):
                if simple_automation.args.diff:
                    try:
                        old_content: Optional[bytes] = conn.download(file=dest)
                    except ValueError:
                        old_content = None
                    op.diff(file=dest, old=old_content, new=content)

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

@operation("upload_content")
def upload_content(content: Union[str, bytes],
                   dest: str,
                   mode: Optional[str] = None,
                   owner: Optional[str] = None,
                   group: Optional[str] = None,
                   name: Optional[str] = None,
                   op: Operation = Operation.internal_use_only) -> OperationResult:
    """
    Uploads the given content as a file to the remote host.

    Parameters
    ----------
    content
        The content to template.
    dest
        The remote destination path.
    mode
        The file mode. Uses the remote execution defaults if None.
    owner
        The file owner. Uses the remote execution defaults if None.
    group
        The file group. Uses the remote execution defaults if None.
    name
        The name for the operation.
    op
        The operation wrapper. Must not be supplied by the user.
    """
    _ = (name) # Processed automatically.
    return _save_content(content, dest, mode, owner, group, op=op)

@operation("upload")
def upload(src: str,
           dest: str,
           mode: Optional[str] = None,
           owner: Optional[str] = None,
           group: Optional[str] = None,
           name: Optional[str] = None,
           op: Operation = Operation.internal_use_only) -> OperationResult:
    """
    Uploads the given file or to the remote host.

    Parameters
    ----------
    src
        The local file to upload.
    dest
        The remote destination path.
    mode
        The file mode. Uses the remote execution defaults if None.
    owner
        The file owner. Uses the remote execution defaults if None.
    group
        The file group. Uses the remote execution defaults if None.
    name
        The name for the operation.
    op
        The operation wrapper. Must not be supplied by the user.
    """
    _ = (name) # Processed automatically.
    with open(src, 'rb') as f:
        return _save_content(f.read(), dest, mode, owner, group, op=op)

@operation("upload_dir")
def upload_dir(src: str,
               dest: str,
               dir_mode: Optional[str] = None,
               file_mode: Optional[str] = None,
               owner: Optional[str] = None,
               group: Optional[str] = None,
               name: Optional[str] = None,
               op: Operation = Operation.internal_use_only) -> OperationResult:
    """
    Uploads the given directory to the remote host. Unrelated files
    in an existing destination directories will be left untouched.

    Given the following source directory:

    .. code-block:: bash
         example/
        └ something.conf

    A trailing slash will cause the folder to become a child of the destination directory.

    .. code-block:: python
        upload_dir("example", "/var/")

    .. code-block:: bash
         /var/
        └  example/
          └ something.conf

    No trailing slash will cause the folder to become the specified folder.

    .. code-block:: python
        upload_dir("example", "/var/myexample")

    .. code-block:: bash
         /var/
        └  myexample/
          └ something.conf

    Parameters
    ----------
    src
        The local directory to upload.
    dest
        The remote destination path for the source directory. If this path
        ends with a slash, the source directory will be uploaded as a child
        of the denoted directory. Otherwise, the uploaded directory will be
        renamed accordingly.
    dir_mode
        The mode for uploaded directories. Includes the base folder. Uses the remote execution defaults if None.
    file_mode
        The mode for uploaded files. Uses the remote execution defaults if None.
    owner
        The owner for all files and directories. Uses the remote execution defaults if None.
    group
        The group for all files and directories. Uses the remote execution defaults if None.
    """
    # TODO "recursive operation". The beginning headline cant be updated afterwards.
    # TODO clean=True operation? i.e. ensure that nothing else is in the specified folder.
    _ = (name) # Processed automatically.
    check_absolute_path(dest)

    if not os.path.isdir(src):
        raise OperationError(f"{src=} must be a directory")

    # If the destination denotes a directory, the actual directory is a
    # child directory thereof with similar name to the source.
    if dest[-1] == "/":
        dest = os.path.join(dest, os.path.basename(src))

    op.desc(dest)
    print()
    with logger.indent():
        # Collect all destination directories and all destination files
        # together with their source counterpart
        dirs: list[str] = [dest]
        files: list[tuple[str, str]] = []
        for root, subdirs, subfiles in os.walk(src):
            root = relpath(root, start=src)
            sroot = normpath(join(src, root))
            droot = normpath(join(dest, root))
            for d in subdirs:
                dirs.append(join(droot, d))
            for f in subfiles:
                files.append((join(sroot, f), join(droot, f)))

        for d in dirs:
            directory(path=d, mode=dir_mode, owner=owner, group=group)
        for sf,df in files:
            upload(src=sf, dest=df, mode=file_mode, owner=owner, group=group)

    # TODO accumulate results, don't create our own (no printing from us)
    return cast(OperationResult, None)

@operation("template_content")
def template_content(content: str,
                     dest: str,
                     context: Optional[dict] = None,
                     mode: Optional[str] = None,
                     owner: Optional[str] = None,
                     group: Optional[str] = None,
                     name: Optional[str] = None,
                     op: Operation = Operation.internal_use_only) -> OperationResult:
    """
    Templates the given content and uploads the result to the remote host.

    Parameters
    ----------
    content
        The content to template.
    dest
        The remote destination path for the file.
    context
        Additional dictionary of variables that will be made available in the template.
    mode
        The file mode. Uses the remote execution defaults if None.
    owner
        The file owner. Uses the remote execution defaults if None.
    group
        The file group. Uses the remote execution defaults if None.
    name
        The name for the operation.
    op
        The operation wrapper. Must not be supplied by the user.
    """
    _ = (name) # Processed automatically.
    try:
        templ = simple_automation.jinja2_env.from_string(content)
        # TODO: make host the "default" context, so abc = host.abc. Also incorporate the given context additionally.
        rendered_content: bytes = templ.render(host=simple_automation.host).encode('utf-8')
    except UndefinedError as e:
        raise OperationError(f"error while templating string: {str(e)}") from e

    return _save_content(rendered_content, dest, mode, owner, group, op=op)

@operation("template")
def template(src: str,
             dest: str,
             context: Optional[dict] = None,
             mode: Optional[str] = None,
             owner: Optional[str] = None,
             group: Optional[str] = None,
             name: Optional[str] = None,
             op: Operation = Operation.internal_use_only) -> OperationResult:
    """
    Templates the given file and uploads the result to the remote host.

    Parameters
    ----------
    src
        The local file to template.
    dest
        The remote destination path for the file.
    context
        Additional dictionary of variables that will be made available in the template.
    mode
        The file mode. Uses the remote execution defaults if None.
    owner
        The file owner. Uses the remote execution defaults if None.
    group
        The file group. Uses the remote execution defaults if None.
    name
        The name for the operation.
    op
        The operation wrapper. Must not be supplied by the user.
    """
    _ = (name) # Processed automatically.
    try:
        templ = simple_automation.jinja2_env.get_template(src)
    except TemplateNotFound as e:
        raise OperationError("template not found: " + str(e)) from e

    try:
        # TODO: make host the "default" context, so abc = host.abc. Also incorporate the given context additionally.
        rendered_content: bytes = templ.render(host=simple_automation.host).encode('utf-8')
    except UndefinedError as e:
        raise OperationError(f"error while templating '{src}': {str(e)}") from e

    return _save_content(rendered_content, dest, mode, owner, group, op=op)

# TODO: unix user, group, user_supplementary_group
# TODO: allow nested operations? if yes, they should nest the logs
#       (maybe indent automatically at begin of each operation.
#       nesting could lead to possible problem/complication with state checking, dry run, etc.
