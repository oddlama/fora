"""
Provides basic transactions.
"""
from jinja2.exceptions import TemplateNotFound, UndefinedError
from simple_automation.context import Context
from simple_automation.exceptions import LogicError, MessageError, RemoteExecError
from simple_automation.checks import check_valid_path
from simple_automation.transactions.utils import template_str, resolve_mode_owner_group, remote_stat, remote_upload
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
    path = template_str(context, path)
        mode, owner, group = resolve_mode_owner_group(context, mode, owner, group, context.dir_mode)
        (cur_ft, cur_mode, cur_owner, cur_group) = remote_stat(context, path)
def directory_all(context: Context, paths: list[str], mode=None, owner=None, group=None):

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
    src = template_str(context, src)
    dst = template_str(context, dst)
    return remote_upload(context, get_content, title="template", name=dst, dst=dst, mode=mode, owner=owner, group=group)
def template_all(context: Context, src_dst_pairs: list[(str, str)], mode=None, owner=None, group=None):

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
    src = template_str(context, src)
    dst = template_str(context, dst)
    return remote_upload(context, get_content, title="copy", name=dst, dst=dst, mode=mode, owner=owner, group=group)
def copy_all(context: Context, src_dst_pairs: list[(str, str)], mode=None, owner=None, group=None):

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
def save_output(context: Context, command: list[str], dst: str, desc=None, mode=None, owner=None, group=None):

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
    command = [template_str(context, c) for c in command]
    dst = template_str(context, dst)
    return remote_upload(context, get_content, title="save out", name=name, dst=dst, mode=mode, owner=owner, group=group)