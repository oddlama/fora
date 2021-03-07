"""
Provides basic transactions.
"""

import os

from jinja2.exceptions import TemplateNotFound, UndefinedError

from simple_automation.context import Context
from simple_automation.exceptions import LogicError, MessageError, RemoteExecError
from simple_automation.checks import check_valid_path
from simple_automation.transactions.utils import template_str, resolve_mode_owner_group, remote_stat, remote_upload

# pylint: disable=W0621

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

def template(context: Context, dst: str, src: str = None, content: str = None, mode=None, owner=None, group=None):
    """
    Templates the given src file or given content and copies the output to the remote host at dst.
    Either content or src must be specified.

    Parameters
    ----------
    context : Context
        The context providing the execution context and templating dictionary.
    src : str, optional
        The local source file path relative to the project directory. Will be templated. Mutually exclusive with content.
    content : str, optional
        The content for the file. Will be templated. Mutually exclusive with src.
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
    if src is not None:
        src = template_str(context, src)
    dst = template_str(context, dst)
    check_valid_path(dst)

    if content is None and src is None:
        raise LogicError("Either src or content must be given.")
    if content is not None and src is not None:
        raise LogicError("Exactly one of src or content must be given.")

    def get_content():
        if content is not None:
            return template_str(context, content)

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

def group(context: Context,
          name: str,
          state: str = "present",
          system: bool = False):
    """
    Creates or deletes a unix group.

    Parameters
    ----------
    context : Context
        The context providing the execution context and templating dictionary.
    name : str
        The name of the user to create or modify. Will be templated.
    state: str
        If "present" the user will be added / modified, if "absent" the user will be deleted ignoring all other parameters.
    system: bool
        If ``True`` the user will be created as a system user. This has no effect on existing users.

    Returns
    -------
    CompletedTransaction
        The completed transaction
    """
    name = template_str(context, name)

    # pylint: disable=R0801
    if state not in ["present", "absent"]:
        raise LogicError(f"Invalid user state '{state}'")

    with context.transaction(title="group", name=name) as action:
        grinfo = context.remote_exec(["python", "-c", (
            'import sys,grp\n'
            'try:\n'
            '    g=grp.getgrnam(sys.argv[1])\n'
            'except KeyError:\n'
            '    print("0")\n'
            '    sys.exit(0)\n'
            'print("1")')
            , name], checked=True)
        exists = grinfo.stdout.strip().startswith('1')

        if state == "absent":
            action.initial_state(exists=exists)
            if not exists:
                return action.unchanged()
            action.final_state(exists=False)

            if not context.pretend:
                try:
                    context.remote_exec(["groupdel", name], checked=True)
                except RemoteExecError as e:
                    return action.failure(e)
        else:
            action.initial_state(exists=exists)
            if exists:
                return action.unchanged()
            action.final_state(exists=True)

            if not context.pretend:
                try:
                    command = ["groupadd"]
                    if system:
                        command.append("--system")
                    command.append(name)
                    context.remote_exec(command, checked=True)
                except RemoteExecError as e:
                    return action.failure(e)

        return action.success()

def user(context: Context,
         name: str,
         group: str = None,
         groups: list[str] = None,
         append_groups: bool = False,
         state: str = "present",
         system: bool = False,
         shell: str = None,
         password: str = None,
         home: str = None,
         create_home = True):
    # pylint: disable=R0912,R0915
    """
    Creates or modifies a unix user. Because we interally call ``userdel``, removing a user will also remove
    it's associated primary group if no other user belongs to it.

    Parameters
    ----------
    context : Context
        The context providing the execution context and templating dictionary.
    name : str
        The name of the user to create or modify. Will be templated.
    group: str, optional
        The primary group of the user. If given, the group must already exists. Otherwise, a group will be created with the same name as the user,
        if a user is created by this action. Will be templated.
    groups: list[str], optional
        Supplementary groups for the user.
    append_groups: bool
        If ``True``, the user will be added to all given supplementary groups. If ``False``, the user will be added to exactly the given supplementary groups and removed from other groups.
    state: str
        If "present" the user will be added / modified, if "absent" the user will be deleted ignoring all other parameters.
    system: bool
        If ``True`` the user will be created as a system user. This has no effect on existing users.
    shell: str
        Specifies the shell for the user. Defaults to ``/sbin/nologin`` if not given but a user needs to be created. Will be templated.
    password : str, optional
        Will update the password hash to the given vaule of the user. Use ``!`` to lock the account.
        Defaults to '!' if not given but a user needs to be created. Will be templated.
        You can generate a password hash by using the following script:

        >>> import crypt, getpass
        >>> crypt.crypt(getpass.getpass(), crypt.mksalt(crypt.METHOD_SHA512))
        '$6$rwn5z9MlYvcnE222$9wOP6Y6EcnF.cZ7BUjttWeSQNdOQWI...'

    home: str, optional
        The home directory for the user. Will be left empty if not given but a user needs to be created. Will be templated.
    create_home: bool
        If ``True`` and home was given, create the home directory of the user if it doesn't exist.

    Returns
    -------
    CompletedTransaction
        The completed transaction
    """
    name     = template_str(context, name)
    group    = template_str(context, group)    if group    is not None else None
    home     = template_str(context, home)     if home     is not None else None
    password = template_str(context, password) if password is not None else None
    shell    = template_str(context, shell)    if shell    is not None else None

    # pylint: disable=R0801
    if state not in ["present", "absent"]:
        raise LogicError(f"Invalid user state '{state}'")

    if home is not None:
        check_valid_path(home)

    with context.transaction(title="user", name=name) as action:
        pwinfo = context.remote_exec(["python", "-c", (
            'import sys,grp,pwd,spwd\n'
            'try:\n'
            '    p=pwd.getpwnam(sys.argv[1])\n'
            'except KeyError:\n'
            '    print("0:")\n'
            '    sys.exit(0)\n'
            'g=grp.getgrgid(p.pw_gid)\n'
            's=spwd.getspnam(p.pw_name)\n'
            'grps=\',\'.join([sg.gr_name for sg in grp.getgrall() if p.pw_name in sg.gr_mem])\n'
            'print(f"1:{g.gr_name}:{grps}:{p.pw_dir}:{p.pw_shell}:{s.sp_pwdp}")')
            , name], checked=True)
        exists = pwinfo.stdout.strip().startswith('1:')
        if exists:
            ( _
            , cur_group
            , cur_groups
            , cur_home
            , cur_shell
            , cur_password
            ) = pwinfo.stdout.strip().split(':')
            cur_groups = list(sorted(set([] if cur_groups == '' else cur_groups.split(','))))
        else:
            cur_group    = None
            cur_groups   = []
            cur_home     = None
            cur_shell    = None
            cur_password = None

        if state == "absent":
            action.initial_state(exists=exists)
            if not exists:
                return action.unchanged()
            action.final_state(exists=False)

            if not context.pretend:
                try:
                    context.remote_exec(["userdel", name], checked=True)
                except RemoteExecError as e:
                    return action.failure(e)
        else:
            action.initial_state(exists=exists, group=cur_group, groups=cur_groups, home=cur_home, shell=cur_shell, pw=cur_password)
            fin_group    = group or cur_group or name
            fin_groups   = cur_groups if groups is None else list(sorted(set(cur_groups + groups if append_groups else groups)))
            fin_home     = home or cur_home
            fin_shell    = shell or cur_shell or '/sbin/nologin'
            fin_password = password or cur_password or '!'
            action.final_state(exists=True, group=fin_group, groups=fin_groups, home=fin_home, shell=fin_shell, pw=fin_password)

            if not context.pretend:
                try:
                    if exists:
                        # Only apply changes to the existing user
                        if cur_group != fin_group:
                            context.remote_exec(["usermod", "--gid", fin_group, name], checked=True)

                        if cur_groups != fin_groups:
                            context.remote_exec(["usermod", "--groups", ','.join(fin_groups), name], checked=True)

                        if cur_home != fin_home:
                            context.remote_exec(["usermod", "--home", fin_home, name], checked=True)

                        if cur_shell != fin_shell:
                            context.remote_exec(["usermod", "--shell", fin_shell, name], checked=True)

                        if cur_password != fin_password:
                            context.remote_exec(["usermod", "--password", fin_password, name], checked=True)
                    else:
                        # Create a new user so that is results in the given final state
                        command = ["useradd"]
                        if system:
                            command.append("--system")

                        # Primary group
                        if group is None:
                            command.append("--user-group")
                        else:
                            command.extend(["--no-user-group", "--gid", group])

                        # Supplementary groups
                        if len(fin_groups) > 0:
                            command.extend(["--groups", ','.join(fin_groups)])

                        command.extend(["--no-create-home", "--home-dir", fin_home or ''])
                        command.extend(["--shell", fin_shell])
                        command.extend(["--password", fin_password])
                        command.append(name)

                        context.remote_exec(command, checked=True)
                except RemoteExecError as e:
                    return action.failure(e)

        # Remember result
        action_result = action.success()

    # Create home directory afterwards if necessary
    if state == "present" and create_home and cur_home is None and fin_home:
        directory(context, path=fin_home, mode=0o700, owner=name, group=fin_group)

    return action_result
