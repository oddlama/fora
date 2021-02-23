"""
Provides basic transaction utilities.
"""

import hashlib
import base64

from jinja2.exceptions import UndefinedError
from jinja2 import Template

from simple_automation.context import Context
from simple_automation.exceptions import LogicError, RemoteExecError

def template_str(context: Context, content : str) -> str:
    """
    Renders the given string template.

    Parameters
    ----------
    context : Context
        The context providing the templating dictionary
    content : str
        The string to template

    Returns
    -------
    str
        The templated string
    """
    templ = Template(content)
    try:
        return templ.render(context.vars_dict)
    except UndefinedError as e:
        raise LogicError(f"Error while templating string '{content}': " + str(e)) from e

def _mode_to_str(mode):
    """
    Stringifies a given octal mode.
    """
    return f"{mode:>03o}"

def resolve_mode_owner_group(context: Context, mode, owner, group, fallback_mode):
    """
    Canonicalize mode, owner and group. If any of them is None, the respective
    variable will be replaced with the context default.

    Parameters
    ----------
    context : Context
        The host execution context
    mode : int
        The mode to canonicalize. May be None.
    owner : str
        User id or name for the owner. User will be verified as existing on the remote.
    group : str
        Group id or name for the group. Group will be verified as existing on the remote.
    fallback_mode : int
        The fallback_mode to canonicalize in case mode = None. Usually set to either context.file_mode or context.dir_mode.

    Returns
    -------
    (str, str, str)
        A tuple of (resolved_mode, resolved_owner, resolved_group)
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

def remote_stat(context, path):
    """
    Runs stat on the given remote path.

    Parameters
    ----------
    context : Context
        The host execution context
    path : str
        The path to run stat on.

    Returns
    -------
    (str, str, str, str)
        A tuple of (file_type, mode, owner, group)
    """
    stat = context.remote_exec(["stat", "-c", "%F;%a;%u;%g", path])
    if stat.return_code == 0:
        file_type, mode, owner, group = stat.stdout.strip().split(";")
        mode, owner, group = resolve_mode_owner_group(context, int(mode, 8), owner, group, None)
        return (file_type, mode, owner, group)
    return (None, None, None, None)

def remote_sha512sum(context: Context, path: str):
    """
    Fetch the sha512sum of a remote file.

    Parameters
    ----------
    context : Context
        The host execution context
    path : str
        The path to the remote file.

    Returns
    -------
    str
        The hexlified sha512sum of the path on the remote host, or None if an error occurred.
    """
    sha512sum = context.remote_exec(["sha512sum", "-b", path])
    if sha512sum.return_code == 0:
        return sha512sum.stdout.strip().split(" ")[0]
    return None

def remote_upload(context: Context, get_content, title: str, name: str, dst: str, mode=None, owner=None, group=None):
    """
    Calls get_content and saves the resulting string as a file on the remote host at dst.
    No arguments will be templated, this is task of the calling function.
    Optionally accepts file mode, owner and group, if not given, context defaults are used.

    Parameters
    ----------
    context : Context
        The host execution context
    get_content : Callable[[],str]
        A function that is called to get the content that should be uploaded.
    title : str
        The title for the generated transaction
    name : str
        The name for the generated transaction
    dst : str
        The remote destination for the uplaoded file
    mode : int, optional
        The new file mode. Defaults the current context file creation mode.
    owner : str, optional
        The new file owner. Defaults the current context owner.
    group : str, optional
        The new file group. Defaults the current context group.

    Returns
    -------
    str
        The hexlified sha512sum of the path on the remote host, or None if an error occurred.
    """
    with context.transaction(title=title, name=name) as action:
        mode, owner, group = resolve_mode_owner_group(context, mode, owner, group, context.file_mode)

        # Query current state
        (cur_ft, cur_mode, cur_owner, cur_group) = remote_stat(context, dst)
        cur_sha512sum = remote_sha512sum(context, dst)

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
