"""
Provides basic transactions.
"""

import os

from jinja2.exceptions import TemplateNotFound, UndefinedError

from simple_automation.context import Context
from simple_automation.exceptions import LogicError, MessageError, RemoteExecError
from simple_automation.checks import check_valid_path
from simple_automation.transactions.utils import template_str, resolve_mode_owner_group, remote_stat, remote_upload

def directory(context: Context, path: str, mode=None, owner=None, group=None):
    """
    Creates the given directory on the remote.

    Parameters
    ----------
    context : Context
        The context providing the execution context and templating dictionary.
    path : str
        The directory path to create (will be templated). Parent directory must exist.
    mode : int, optional
        The new directory mode. Defaults the current context directory creation mode.
    owner : str, optional
        The new directory owner. Defaults the current context owner.
    group : str, optional
        The new directory group. Defaults the current context group.

    Returns
    -------
    CompletedTransaction
        The completed transaction
    """
    path = template_str(context, path)
    check_valid_path(path)
    with context.transaction(title="dir", name=path) as action:
        mode, owner, group = resolve_mode_owner_group(context, mode, owner, group, context.dir_mode)

        # Get current state
        (cur_ft, cur_mode, cur_owner, cur_group) = remote_stat(context, path)
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

def directory_all(context: Context, paths: list[str], mode=None, owner=None, group=None):
    """
    Creates the given directories as if directory() was called for each of them.

    Parameters
    ----------
    context : Context
        The context providing the execution context and templating dictionary.
    paths : str
        The directory paths to create (each will be templated). Parent directory must exist for each directory. Executed in order.
    mode : int, optional
        The new directory mode. Defaults the current context directory creation mode.
    owner : str, optional
        The new directory owner. Defaults the current context owner.
    group : str, optional
        The new directory group. Defaults the current context group.

    Returns
    -------
    CompletedTransaction
        The completed transaction
    """
    for path in paths:
        directory(context, path, mode, owner, group)

def template(context: Context, src: str, dst: str, mode=None, owner=None, group=None):
    """
    Templates the given src file and copies the output to the remote host at dst.

    Parameters
    ----------
    context : Context
        The context providing the execution context and templating dictionary.
    src : str
        The local source file path relative to the project directory. Will be templated.
    dst : str
        The remote destination file path. Will be templated.
    mode : int, optional
        The new file mode. Defaults the current context file creation mode.
    owner : str, optional
        The new file owner. Defaults the current context owner.
    group : str, optional
        The new file group. Defaults the current context group.

    Returns
    -------
    CompletedTransaction
        The completed transaction
    """
    src = template_str(context, src)
    dst = template_str(context, dst)
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

    return remote_upload(context, get_content, title="template", name=dst, dst=dst, mode=mode, owner=owner, group=group)

def template_all(context: Context, src_dst_pairs: list[(str, str)], mode=None, owner=None, group=None):
    """
    Templates each (src, dst) list entry, as if template() was called for each of them.

    Parameters
    ----------
    context : Context
        The context providing the execution context and templating dictionary.
    src_dst_pairs : list[(str, str)]
        A list of (src, dst) pairs corresponding to the parameters from template().
    mode : int, optional
        The new file mode. Defaults the current context file creation mode.
    owner : str, optional
        The new file owner. Defaults the current context owner.
    group : str, optional
        The new file group. Defaults the current context group.

    Returns
    -------
    CompletedTransaction
        The completed transaction
    """
    for src,dst in src_dst_pairs:
        template(context, src, dst, mode, owner, group)

def copy(context: Context, src: str, dst: str, mode=None, owner=None, group=None):
    """
    Copies the given src file to the remote host at dst.

    Parameters
    ----------
    context : Context
        The context providing the execution context and templating dictionary.
    src : str
        The local source file path relative to the project directory. Will be templated.
    dst : str
        The remote destination file path. Will be templated.
    mode : int, optional
        The new file mode. Defaults the current context file creation mode.
    owner : str, optional
        The new file owner. Defaults the current context owner.
    group : str, optional
        The new file group. Defaults the current context group.

    Returns
    -------
    CompletedTransaction
        The completed transaction
    """
    src = template_str(context, src)
    dst = template_str(context, dst)
    check_valid_path(dst)

    def get_content():
        # Get source content
        with open(os.path.join(context.host.manager.main_directory, src), 'r') as f:
            return f.read()

    return remote_upload(context, get_content, title="copy", name=dst, dst=dst, mode=mode, owner=owner, group=group)

def copy_all(context: Context, src_dst_pairs: list[(str, str)], mode=None, owner=None, group=None):
    """
    Copies each (src, dst) list entry, as if copy() was called for each of them.

    Parameters
    ----------
    context : Context
        The context providing the execution context and templating dictionary.
    src_dst_pairs : list[(str, str)]
        A list of (src, dst) pairs corresponding to the parameters from copy().
    mode : int, optional
        The new file mode. Defaults the current context file creation mode.
    owner : str, optional
        The new file owner. Defaults the current context owner.
    group : str, optional
        The new file group. Defaults the current context group.

    Returns
    -------
    CompletedTransaction
        The completed transaction
    """
    for src,dst in src_dst_pairs:
        copy(context, src, dst, mode, owner, group)

def save_output(context: Context, command: list[str], dst: str, desc=None, mode=None, owner=None, group=None):
    """
    Saves the stdout of the given command on the remote host at remote dst.
    Using --pretend will still run the command, but won't save the output.
    Changed status reflects if the file contents changed.
    Optionally accepts file mode, owner and group, if not given, context defaults are used.

    Parameters
    ----------
    context : Context
        The context providing the execution context and templating dictionary.
    command: list[str]
        A list containing the command and its arguments. Each one will be templated.
    dst : str
        The remote destination file path. Will be templated.
    desc : str
        A description to be printed in the summary when executing.
    mode : int, optional
        The new file mode. Defaults the current context file creation mode.
    owner : str, optional
        The new file owner. Defaults the current context owner.
    group : str, optional
        The new file group. Defaults the current context group.

    Returns
    -------
    CompletedTransaction
        The completed transaction
    """
    command = [template_str(context, c) for c in command]
    dst = template_str(context, dst)
    check_valid_path(dst)

    def get_content():
        # Get command output
        return context.remote_exec(command, checked=True).stdout

    name = f"{command}" if desc is None else desc
    return remote_upload(context, get_content, title="save out", name=name, dst=dst, mode=mode, owner=owner, group=group)
