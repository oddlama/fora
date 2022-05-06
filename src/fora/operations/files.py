"""Provides operations related to creating and modifying files and directories."""

import os
import re
from datetime import datetime, timezone
from os.path import join, relpath, normpath
from typing import Optional, Union

from jinja2 import Environment, StrictUndefined, Template
from jinja2.exceptions import UndefinedError

import fora
from fora import logger
from fora.operations.api import Operation, OperationResult, operation
from fora.operations.utils import check_absolute_path, save_content

_jinja2_env: Environment = Environment(
    autoescape=False,
    undefined=StrictUndefined)
"""The jinja2 environment used for templating."""

def _render_template(templ: Template, context: Optional[dict]) -> bytes:
    """
    Renders the given template with the additional variables provided context (if any).

    All host variables, including inherited variables will be available
    as-is in the template. Any variable provided via the context will
    also be made available, overshadowing existing variables.

    The current host and inventory will always be added under the keys
    `"host"` and `"inventory"` respectively, shadowing other variables,
    to ensure these objects are always accessible.

    Parameters
    ----------
    templ
        The template to render.
    context
        The additional rendering context. Overwrites any implicit templating variables from the host.

    Returns
    -------
    bytes
        The utf-8 encoded rendered template.
    """

    dvars = fora.host.vars_hierarchical()
    if context is not None:
        dvars.update(context)
    dvars["host"] = fora.host
    dvars["inventory"] = fora.host
    return templ.render(dvars).encode("utf-8")

@operation("dir")
def directory(path: str,
              present: bool = True,
              touch: bool = False,
              mode: Optional[str] = None,
              owner: Optional[str] = None,
              group: Optional[str] = None,
              name: Optional[str] = None,
              check: bool = True,
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
    check
        If True, returning `op.failure()` will raise an OperationError. All manually raised
        OperationErrors will be propagated. When False, any manually raised OperationError will
        be caught and `op.failure()` will be returned with the given message while continuing execution.
    op
        The operation wrapper. Must not be supplied by the user.
    """
    # pylint: disable=too-many-branches
    _ = (name, check) # Processed automatically.
    check_absolute_path(path, f"{path=}")
    op.desc(path)

    conn = fora.host.connection
    with op.defaults(dir_mode=mode, owner=owner, group=group) as attr:
        if present:
            op.final_state(exists=True, mode=attr.dir_mode, owner=attr.owner, group=attr.group, touched=touch)
        else:
            op.final_state(exists=False, mode=None, owner=None, group=None, touched=False)

        # Examine current state
        stat = conn.stat(path)
        if stat is None:
            # The directory doesn't exist
            op.initial_state(exists=False, mode=None, owner=None, group=None, touched=False)
        else:
            if stat.type != "dir":
                return op.failure(f"path '{path}' exists but is not a directory!")

            # The directory exists but may have different attributes
            op.initial_state(exists=True, mode=stat.mode, owner=stat.owner, group=stat.group, touched=False)

        # Return success if nothing needs to be changed
        if op.unchanged():
            return op.success()

        # Apply actions to reach desired state, but only if we are not doing a dry run
        if not fora.args.dry:
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
         check: bool = True,
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
    check
        If True, returning `op.failure()` will raise an OperationError. All manually raised
        OperationErrors will be propagated. When False, any manually raised OperationError will
        be caught and `op.failure()` will be returned with the given message while continuing execution.
    op
        The operation wrapper. Must not be supplied by the user.
    """
    _ = (name, check) # Processed automatically.
    check_absolute_path(path, f"{path=}")
    op.desc(path)

    conn = fora.host.connection
    with op.defaults(file_mode=mode, owner=owner, group=group) as attr:
        if present:
            op.final_state(exists=True, mode=attr.file_mode, owner=attr.owner, group=attr.group, touched=touch)
        else:
            op.final_state(exists=False, mode=None, owner=None, group=None, touched=False)

        # Examine current state
        stat = conn.stat(path)
        if stat is None:
            # The file doesn't exist
            op.initial_state(exists=False, mode=None, owner=None, group=None, touched=False)
        else:
            if stat.type != "file":
                return op.failure(f"path '{path}' exists but is not a file!")

            # The file exists but may have different attributes
            op.initial_state(exists=True, mode=stat.mode, owner=stat.owner, group=stat.group, touched=False)

        # Return success if nothing needs to be changed
        if op.unchanged():
            return op.success()

        # Apply actions to reach desired state, but only if we are not doing a dry run
        if not fora.args.dry:
            if present:
                # Create file if it doesn't exist
                # or touch file if requested
                if op.changed("exists") or op.changed("touched"):
                    conn.run(["touch", "--", path])

                # Set correct mode, if needed
                if op.changed("mode"):
                    conn.run(["chmod", attr.file_mode, "--", path])

                # Set correct owner and group, if needed
                if op.changed("owner") or op.changed("group"):
                    conn.run(["chown", f"{attr.owner}:{attr.group}", "--", path])
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
         check: bool = True,
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
    check
        If True, returning `op.failure()` will raise an OperationError. All manually raised
        OperationErrors will be propagated. When False, any manually raised OperationError will
        be caught and `op.failure()` will be returned with the given message while continuing execution.
    op
        The operation wrapper. Must not be supplied by the user.
    """
    # pylint: disable=too-many-branches
    _ = (name, check) # Processed automatically.
    check_absolute_path(path, f"{path=}")
    if not target:
        raise ValueError("Link target cannot be empty")
    op.desc(path)

    conn = fora.host.connection
    with op.defaults(owner=owner, group=group) as attr:
        if present:
            op.final_state(exists=True, target=target, owner=attr.owner, group=attr.group, touched=touch)
        else:
            op.final_state(exists=False, target=None, owner=None, group=None, touched=False)

        # Examine current state
        stat = conn.stat(path)
        if stat is None:
            # The link doesn't exist
            op.initial_state(exists=False, target=None, owner=None, group=None, touched=False)
        else:
            if stat.type != "link":
                return op.failure(f"path '{path}' exists but is not a link!")

            existing_target = conn.run(["readlink", "-n", path])
            # The link exists but may have a different target or different attributes
            op.initial_state(exists=True, target=(existing_target.stdout or b"").decode(), owner=stat.owner, group=stat.group, touched=False)

        # Return success if nothing needs to be changed
        if op.unchanged():
            return op.success()

        # Apply actions to reach desired state, but only if we are not doing a dry run
        if not fora.args.dry:
            if present:
                # Create link if it doesn't exist
                if op.changed("target"):
                    conn.run(["ln", "-sf", "--", target, path])

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

@operation("upload_content")
def upload_content(content: Union[str, bytes],
                   dest: str,
                   mode: Optional[str] = None,
                   owner: Optional[str] = None,
                   group: Optional[str] = None,
                   name: Optional[str] = None,
                   check: bool = True,
                   op: Operation = Operation.internal_use_only) -> OperationResult:
    """
    Uploads the given content as a file to the remote host.

    Parameters
    ----------
    content
        The content to upload.
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
    check
        If True, returning `op.failure()` will raise an OperationError. All manually raised
        OperationErrors will be propagated. When False, any manually raised OperationError will
        be caught and `op.failure()` will be returned with the given message while continuing execution.
    op
        The operation wrapper. Must not be supplied by the user.
    """
    _ = (name, check) # Processed automatically.
    check_absolute_path(dest, f"{dest=}")
    op.desc(dest)
    return save_content(op, content, dest, mode, owner, group)

@operation("upload")
def upload(src: str,
           dest: str,
           mode: Optional[str] = None,
           owner: Optional[str] = None,
           group: Optional[str] = None,
           name: Optional[str] = None,
           check: bool = True,
           op: Operation = Operation.internal_use_only) -> OperationResult:
    """
    Uploads the given file or to the remote host. Overwrites existing files.

    Parameters
    ----------
    src
        The local file to upload.
    dest
        The remote destination path. If this ends in a slash, the basename of the source file is automatically appended.
    mode
        The file mode. Uses the remote execution defaults if None.
    owner
        The file owner. Uses the remote execution defaults if None.
    group
        The file group. Uses the remote execution defaults if None.
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
    check_absolute_path(dest, f"{dest=}")
    if dest.endswith("/"):
        dest = os.path.join(dest, os.path.basename(src))
    op.desc(dest)
    with open(src, 'rb') as f:
        return save_content(op, f.read(), dest, mode, owner, group)

@operation("upload_dir")
def upload_dir(src: str,
               dest: str,
               dir_mode: Optional[str] = None,
               file_mode: Optional[str] = None,
               owner: Optional[str] = None,
               group: Optional[str] = None,
               name: Optional[str] = None,
               check: bool = True,
               op: Operation = Operation.internal_use_only) -> OperationResult:
    """
    Uploads the given directory to the remote host. Unrelated files
    in an existing destination directories will be left untouched.
    This will only upload files and directories, not links or other special files.

    Given the following source directory:

    ```python
     example/
    └ something.conf
    ```

    A trailing slash will cause the folder to become a child of the destination directory.

    ```python
    upload_dir("example", "/var/")

     /var/
    └  example/
        └ something.conf
    ```

    No trailing slash will cause the folder to become the specified folder.

    ```python
    upload_dir("example", "/var/myexample")

     /var/
    └  myexample/
        └ something.conf
    ```

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
    # TODO: clean=True operation? i.e. ensure that nothing else is in the specified folder.
    _ = (name, check) # Processed automatically.
    op.nested(True)

    check_absolute_path(dest, f"{dest=}")
    if not os.path.isdir(src):
        raise ValueError(f"{src=} must be a directory")

    # If the destination denotes a directory, the actual directory is a
    # child directory thereof with similar name to the source.
    if dest[-1] == "/":
        dest = os.path.join(dest, os.path.basename(src))

    op.desc(dest)
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
            op.add_nested_result(d, directory(path=d, mode=dir_mode, owner=owner, group=group))
        for sf,df in files:
            if os.path.isfile(sf):
                op.add_nested_result(df, upload(src=sf, dest=df, mode=file_mode, owner=owner, group=group))

    return op.success()

@operation("template_content")
def template_content(content: str,
                     dest: str,
                     context: Optional[dict] = None,
                     mode: Optional[str] = None,
                     owner: Optional[str] = None,
                     group: Optional[str] = None,
                     name: Optional[str] = None,
                     check: bool = True,
                     op: Operation = Operation.internal_use_only) -> OperationResult:
    """
    Templates the given content and uploads the result to the remote host.
    See `fora.operations.files.template` for more information about the available variables in the template.

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
    check
        If True, returning `op.failure()` will raise an OperationError. All manually raised
        OperationErrors will be propagated. When False, any manually raised OperationError will
        be caught and `op.failure()` will be returned with the given message while continuing execution.
    op
        The operation wrapper. Must not be supplied by the user.
    """
    _ = (name, check) # Processed automatically.
    check_absolute_path(dest, f"{dest=}")
    op.desc(dest)

    try:
        templ = _jinja2_env.from_string(content)
        rendered_content = _render_template(templ, context)
    except UndefinedError as e:
        raise ValueError(f"Error while templating string: {str(e)}") from None

    return save_content(op, rendered_content, dest, mode, owner, group)

@operation("template")
def template(src: str,
             dest: str,
             context: Optional[dict] = None,
             mode: Optional[str] = None,
             owner: Optional[str] = None,
             group: Optional[str] = None,
             name: Optional[str] = None,
             check: bool = True,
             op: Operation = Operation.internal_use_only) -> OperationResult:
    """
    Templates the given file and uploads the result to the remote host.
    All host variables, including inherited variables will be available
    as-is in the template. Any variable provided via the context will
    also be made available, overshadowing existing variables.

    The current host and inventory will always be added under the keys
    `"host"` and `"inventory"` respectively, shadowing other variables,
    to ensure these objects are always accessible.

    Parameters
    ----------
    src
        The local file to template.
    dest
        The remote destination path. If this ends in a slash, the basename of the source file is automatically appended.
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
    check
        If True, returning `op.failure()` will raise an OperationError. All manually raised
        OperationErrors will be propagated. When False, any manually raised OperationError will
        be caught and `op.failure()` will be returned with the given message while continuing execution.
    op
        The operation wrapper. Must not be supplied by the user.
    """
    _ = (name, check) # Processed automatically.
    check_absolute_path(dest, f"{dest=}")
    if dest.endswith("/"):
        dest = os.path.join(dest, os.path.basename(src))
    op.desc(dest)

    with open(src, "r", encoding="utf-8") as f:
        content = f.read()

    try:
        templ = _jinja2_env.from_string(content)
        rendered_content = _render_template(templ, context)
    except UndefinedError as e:
        raise ValueError(f"Error while templating '{src}': {str(e)}") from None

    return save_content(op, rendered_content, dest, mode, owner, group)

@operation("line")
def line(path: str,
         line: str, # pylint: disable=redefined-outer-name
         present: bool = True,
         regex: Optional[str] = None,
         ignore_whitespace: bool = True,
         backup: Union[bool, str] = False,
         name: Optional[str] = None,
         check: bool = True,
         op: Operation = Operation.internal_use_only) -> OperationResult:
    """
    Manage a line in a file. New lines will be added to the end of the file.
    If the file does not exist, it will be created with the current default file_mode, owner and group.

    Parameters
    ----------
    path
        The file in question.
    line
        The line that should be added or removed. If present is `False` and regex is set,
        this parameter is not used.
    present
        Whether the line should exist in the file.
    regex
        A regex to search for in the existing file to determine whether the line exists.
        Partial matches in a line (when for example not using `^...$`) count as matching the entire line.
        Uses standard python regular expression. If `None`, the given line will be searched for literally.
    ignore_whitespace
        Whether whitespace before and after the line should be ignored when searching for the line.
        This affects both the provided line and lines in an existing file.
        This does not affect the actual line that will be put into the file if it isn't found.
        This parameter is ignored if `regex` was specified.
    backup
        Whether to backup the old file if any changes will be made. If this is `True`,
        the old file will be copied to a new file with `.{date}.bak`, appended to the end of the filename.
        `date` will be replaced with the current date and time in ISO 8601 UTC format.
        You pass a string instead of a boolean to enable this option while specifying the new filename manually,
        relative to the original file.
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
    check_absolute_path(path, f"{path=}")
    op.desc(path)

    conn = fora.host.connection
    with op.defaults() as attr:
        op.final_state(line_present=present)

        orig_bytes: Optional[bytes] = None
        orig_content: Optional[str] = None
        line_present: bool = False

        # Examine current state
        stat = conn.stat(path)
        if stat is not None:
            if stat.type != "file":
                return op.failure(f"path '{path}' exists but is not a file!")

            # Download the current file
            orig_bytes = conn.download(path)
            orig_content = orig_bytes.decode("utf-8", errors="surrogateescape")

            # Check whether the line is already contained
            if regex is None:
                if ignore_whitespace:
                    line_present = line.strip() in [l.strip() for l in (orig_content or "").splitlines()]
                else:
                    line_present = line in (orig_content or "").splitlines()
            else:
                line_present = bool(re.search(regex, orig_content, re.MULTILINE))

        op.initial_state(line_present=line_present)

        # Return success if nothing needs to be changed
        if op.unchanged():
            return op.success()

        lines = (orig_content or "").splitlines()
        if present:
            lines.append(line)
        else:
            # Remove matching lines
            if regex is None:
                if ignore_whitespace:
                    lines = list(filter(lambda l: line != l.strip(), lines))
                else:
                    lines = list(filter(lambda l: line != l, lines))
            else:
                # mypy false positive here, ignore type warning
                lines = list(filter(lambda l: not re.search(regex, l), lines)) # type: ignore[type-var]

        new_content = "\n".join(lines) + "\n"
        new_bytes = new_content.encode("utf-8", errors="surrogateescape")

        # Add diff if desired
        if fora.args.diff:
            op.diff(path, orig_bytes, new_bytes)

        # Apply actions to reach desired state, but only if we are not doing a dry run
        if not fora.args.dry:
            if orig_bytes is None:
                conn.upload(file=path, content=new_bytes, mode=attr.file_mode, owner=attr.owner, group=attr.group)
            else:
                if backup:
                    if isinstance(backup, bool):
                        backup = f".{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}.bak"
                    conn.run(["cp", "-a", "--", path, os.path.join(os.path.dirname(path), backup)])
                conn.upload(file=path, content=new_bytes)

        return op.success()
