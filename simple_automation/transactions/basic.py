"""
Provides basic transactions.
"""

import hashlib
import base64
import os

from jinja2.exceptions import TemplateNotFound, UndefinedError
from jinja2 import Template

from simple_automation.context import Context
from simple_automation.exceptions import LogicError, MessageError, RemoteExecError
from simple_automation.checks import check_valid_path

def _template_str(context: Context, template_str):
    """
    Renders the given string template.
    """
    templ = Template(template_str)
    try:
        return templ.render(context.vars_dict)
    except UndefinedError as e:
        raise LogicError(f"Error while templating string '{template_str}': " + str(e)) from e

def _mode_to_str(mode):
    """
    Stringifies a given octal mode.
    """
    return f"{mode:>03o}"

def _resolve_mode_owner_group(context: Context, mode, owner, group, fallback_mode):
    """
    Canonicalize mode, owner and group. If any of them is None, the respective
    variable will be replaced with the context default.
    """
    # Resolve mode to string
    resolved_mode = _mode_to_str(fallback_mode if mode is None else mode)

    # Resolve owner name/uid to name
    owner = context.owner if owner is None else owner
    remote_cmd_owner_id = context.remote_exec(["id", "-nu", owner])
    if remote_cmd_owner_id.return_code != 0:
        raise LogicError(f"Could not resolve remote user '{owner}'")
    resolved_owner = remote_cmd_owner_id.stdout.strip()

    # Resolve group name/gid to name
    group = context.group if group is None else group
    remote_cmd_group_id = context.remote_exec(["id", "-ng", group])
    if remote_cmd_group_id.return_code != 0:
        raise LogicError(f"Could not resolve remote group '{group}'")
    resolved_group = remote_cmd_group_id.stdout.strip()

    # Return resolved tuple
    return (resolved_mode, resolved_owner, resolved_group)

def _remote_stat(context, path):
    """
    Returns (file_type, mode, owner, group) tuple for a given remote path.
    """
    stat = context.remote_exec(["stat", "-c", "%F;%a;%u;%g", path])
    if stat.return_code == 0:
        file_type, mode, owner, group = stat.stdout.strip().split(";")
        mode, owner, group = _resolve_mode_owner_group(context, int(mode, 8), owner, group, None)
        return (file_type, mode, owner, group)
    return (None, None, None, None)

def _remote_sha512sum(context: Context, path: str):
    """
    Returns the hexlified sha512sum of the path on the remote host,
    or None if an error occurred.
    """
    sha512sum = context.remote_exec(["sha512sum", "-b", path])
    if sha512sum.return_code == 0:
        return sha512sum.stdout.strip().split(" ")[0]
    return None

def _remote_upload(context: Context, get_content, title: str, name: str, dst: str, mode=None, owner=None, group=None):
    """
    Calls get_content and saves the resulting string as a file on the remote host at dst.
    No arguments will be templated, this is task of the calling function.
    Optionally accepts file mode, owner and group, if not given, context defaults are used.
    """
    with context.transaction(title=title, name=name) as action:
        mode, owner, group = _resolve_mode_owner_group(context, mode, owner, group, context.file_mode)

        # Query current state
        (cur_ft, cur_mode, cur_owner, cur_group) = _remote_stat(context, dst)
        cur_sha512sum = _remote_sha512sum(context, dst)

        # Record this initial state
        if cur_ft is None:
            action.initial_state(exists=False, sha512sum=None, mode=None, owner=None, group=None)
        elif cur_ft == "regular file":
            action.initial_state(exists=True, sha512sum=cur_sha512sum, mode=cur_mode, owner=cur_owner, group=cur_group)
        else:
            raise LogicError("Cannot create file on remote: Path already exists and is not a file")

        # Get content
        try:
            content = get_content()
        except Exception as e:
            action.failure(e, set_final_state=True)
            raise e
        sha512sum = hashlib.sha512(content.encode("utf-8")).hexdigest()

        if cur_ft == "regular file":
            if sha512sum == cur_sha512sum and mode == cur_mode and owner == cur_owner and group == cur_group:
                return action.unchanged()

        # Record the final state
        action.final_state(exists=True, sha512sum=sha512sum, mode=mode, owner=owner, group=group)
        # Apply actions to reach new state, if we aren't in pretend mode
        if not context.pretend:
            try:
                # Replace file
                dst_base64 = base64.b64encode(dst.encode('utf-8')).decode('utf-8')
                context.remote_exec(["sh", "-c", f"cat > \"$(echo '{dst_base64}' | base64 -d)\""], checked=True, stdin=content)

                # Set permissions
                context.remote_exec(["chown", f"{owner}:{group}", dst], checked=True)
                context.remote_exec(["chmod", mode, dst], checked=True)
            except RemoteExecError as e:
                return action.failure(e)

        # Return success
        return action.success()

def directory(context: Context, path: str, mode=None, owner=None, group=None):
    """
    Creates the given directory on the remote. Will use the context default
    permissions if not explicitly given.
    """
    path = _template_str(context, path)
    check_valid_path(path)
    with context.transaction(title="dir", name=path) as action:
        mode, owner, group = _resolve_mode_owner_group(context, mode, owner, group, context.dir_mode)

        # Get current state
        (cur_ft, cur_mode, cur_owner, cur_group) = _remote_stat(context, path)
        # Record this initial state
        if cur_ft is None:
            action.initial_state(exists=False, mode=None, owner=None, group=None)
        elif cur_ft == "directory":
            action.initial_state(exists=True, mode=cur_mode, owner=cur_owner, group=cur_group)
            if mode == cur_mode and owner == cur_owner and group == cur_group:
                return action.unchanged()
        else:
            raise LogicError("Cannot create directory on remote: Path already exists and is not a directory")

        # Record the final state
        action.final_state(exists=True, mode=mode, owner=owner, group=group)
        # Apply actions to reach new state, if we aren't in pretend mode
        if not context.pretend:
            try:
                # If stat failed, the directory doesn't exist and we need to create it.
                if cur_ft is None:
                    context.remote_exec(["mkdir", path], checked=True)

                # Set permissions
                context.remote_exec(["chown", f"{owner}:{group}", path], checked=True)
                context.remote_exec(["chmod", mode, path], checked=True)
            except RemoteExecError as e:
                return action.failure(e)

        # Return success
        return action.success()

def directory_all(context: Context, paths: list, mode=None, owner=None, group=None):
    """
    Creates the given directories as if directory() was called for each of them.
    """
    for path in paths:
        directory(context, path, mode, owner, group)

def template(context: Context, src: str, dst: str, mode=None, owner=None, group=None):
    """
    Templates the given src file (relative to your project directory),
    and copies the output to the remote host at dst. Optionally accepts file mode, owner and group,
    if not given, context defaults are used.
    """
    src = _template_str(context, src)
    dst = _template_str(context, dst)
    check_valid_path(dst)

    def get_content():
        # Get templated content
        try:
            templ = context.host.manager.jinja2_env.get_template(src)
        except TemplateNotFound as e:
            raise LogicError("Template not found: " + str(e)) from e

        try:
            return templ.render(context.vars_dict)
        except UndefinedError as e:
            raise MessageError(f"Error while templating '{src}': " + str(e)) from e

    return _remote_upload(context, get_content, title="template", name=dst, dst=dst, mode=mode, owner=owner, group=group)

def template_all(context: Context, src_dst_pairs: list, mode=None, owner=None, group=None):
    """
    Templates each (src, dst) list entry, as if template() was called for each of them.
    """
    for src,dst in src_dst_pairs:
        template(context, src, dst, mode, owner, group)

def copy(context: Context, src: str, dst: str, mode=None, owner=None, group=None):
    """
    Copies the given src file (relative to your project directory) to the remote host at dst.
    Optionally accepts file mode, owner and group, if not given, context defaults are used.
    """
    src = _template_str(context, src)
    dst = _template_str(context, dst)
    check_valid_path(dst)

    def get_content():
        # Get source content
        with open(os.path.join(context.host.manager.main_directory, src), 'r') as f:
            return f.read()

    return _remote_upload(context, get_content, title="copy", name=dst, dst=dst, mode=mode, owner=owner, group=group)

def copy_all(context: Context, src_dst_pairs: list, mode=None, owner=None, group=None):
    """
    Copies each (src, dst) list entry, as if copy() was called for each of them.
    """
    for src,dst in src_dst_pairs:
        copy(context, src, dst, mode, owner, group)

def save_output(context: Context, command: list, dst: str, desc=None, mode=None, owner=None, group=None):
    """
    Saves the stdout of the given command on the remote host at remote dst.
    Using --pretend will still run the command, but won't save the output.
    Changed status reflects if the file contents changed.
    Optionally accepts file mode, owner and group, if not given, context defaults are used.
    """
    command = [_template_str(context, c) for c in command]
    dst = _template_str(context, dst)
    check_valid_path(dst)

    def get_content():
        # Get command output
        return context.remote_exec(command, checked=True).stdout

    name = f"{command}" if desc is None else desc
    return _remote_upload(context, get_content, title="save out", name=name, dst=dst, mode=mode, owner=owner, group=group)
