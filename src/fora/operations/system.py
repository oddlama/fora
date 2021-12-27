"""Provides operations related to the operating system such as user, group or service management."""

from typing import Optional, cast

from fora import globals as G
from fora.operations import utils
from fora.operations.api import Operation, OperationResult, operation
from fora.operations.utils import find_command, new_op_fail
import fora.host

@operation("user")
def user(user: str, # pylint: disable=redefined-outer-name,too-many-statements
         present: bool = True,
         uid: Optional[int] = None,
         group: Optional[str] = None, # pylint: disable=redefined-outer-name
         groups: Optional[list[str]] = None,
         append_groups: bool = False,
         system: bool = False,
         password_hash: Optional[str] = None,
         home: Optional[str] = None,
         shell: Optional[str] = None,
         comment: Optional[str] = None,
         name: Optional[str] = None,
         check: bool = True,
         op: Operation = Operation.internal_use_only) -> OperationResult:
    """
    Creates, modifies or deletes a unix user.

    The home directory for the given user will never be created.
    Use `fora.operations.files.directory` to do this.

    When a user is deleted, it's primary group will also be deleted if no other user
    has the same primary group. This is a quirk of the `userdel` tool, and applies when
    USERGROUPS_ENAB is set to yes in `/etc/login.defs` (which is the case on most distributions).

    Similarly, when a user is created and no primary group is specified, a new primary group with
    the same name as the user will be created for it. As for deletion, this only applies when
    USERGROUPS_ENAB is set to yes in `/etc/login.defs`.

    You can generate a password hash by using the following code:

    ```python
    import crypt, getpass
    real_pw = getpass.getpass()
    password_hash = crypt.crypt(real_pw, crypt.mksalt(crypt.METHOD_SHA512))
    ```

    ### Example:

    ```python
    system.user(
        name="Create a new user for some service including a group of the same name",
        user="testuser")

    system.user(
        name="Create a new user with an existing primary group",
        user="testuser",
        group="users")

    system.user(
        name="Add myuser to the video group",
        user="myuser",
        groups=["video"],
        append_groups=True)

    system.user(
        name="Delete testuser. Will also delete the corresponding primary group if it isn't used for anything else",
        user="testuser",
        present=False)
    ```

    Parameters
    ----------
    user
        The name of the user.
    present
        Whether the given user should exists. If False any existing user with that name will be deleted and all other parameters ignored.
    uid
        The uid for the user. Automatically determined if not specified.
    group
        The primary group (name or gid) for the user. If given, the group must already exists.
        Otherwise, a group will be created with the same name as the user, if USERGROUPS_ENAB is set in /etc/login.defs.
    groups
        Secondary groups for the user.
    append_groups
        Only applies when `groups` were given.
        If `False`, the user will be removed from any groups other than the given ones.
        Otherwise, the user will be appended to the given groups.
    system
        If `True` the user will be created as a system user. This doesn't affect existing users.
    password_hash
        The password hash for the user as given by `crypt(3)`.
        Defaults to '!' if not given but a user needs to be created.
    home
        The home directory for the user. Defaults to `/dev/null` if not given but a user needs to be created.
    shell
        Specifies the shell for the user. Defaults to `/sbin/nologin` if not given but a user needs to be created.
    comment
        Specifies the GECOS comment for the user. Will be left empty if not given but a user needs to be created.
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

    if groups is not None and not isinstance(groups, list):
        raise ValueError("groups must be a list!")

    # Examine current state
    current = conn.query_user(user=user)
    if current is None:
        op.initial_state(exists=False, uid=None, group=None, groups=[], comment=None, home=None, shell=None, password_hash=None)
    else:
        op.initial_state(exists=True, uid=current.uid, group=current.group, groups=current.groups, comment=current.gecos, home=current.home, shell=current.shell, password_hash=current.password_hash)

    # Calculate target state. None means no-desired-value (i.e. keep as-is or use default on creation)
    target_uid = uid or (current.uid if current else None)
    target_group = group or (current.group if current else None)
    if append_groups:
        target_groups = sorted(list(set((groups or []) + (current.groups if current else []))))
    else:
        target_groups = groups or (current.groups if current else [])
    target_password_hash = password_hash or (current.password_hash if current else None)
    target_comment = comment or (current.gecos if current else None)
    target_home = home or (current.home if current else '/dev/null')
    target_shell = shell or (current.shell if current else '/sbin/nologin')

    if present:
        op.final_state(exists=True, uid=target_uid, group=target_group, groups=target_groups, comment=target_comment, home=target_home, shell=target_shell, password_hash=target_password_hash)
    else:
        op.final_state(exists=False, uid=None, group=None, groups=[], comment=None, home=None, shell=None, password_hash=None)

    # Return success if nothing needs to be changed
    if op.unchanged():
        return op.success()

    # Apply actions to reach desired state, but only if we are not doing a dry run
    if not G.args.dry:
        if op.changed("exists"):
            if present:
                # Create new user
                create_command = ["useradd"]
                if system:
                    create_command.append("--system")

                if target_uid is not None:
                    create_command.extend(["--uid", str(target_uid)])

                # Primary group
                if target_group is None:
                    create_command.append("--user-group")
                else:
                    create_command.extend(["--no-user-group", "--gid", target_group])

                # Supplementary groups
                if len(target_groups) > 0:
                    create_command.extend(["--groups", ','.join(target_groups)])

                # Comment
                if target_comment is not None:
                    create_command.extend(["--comment", target_comment])

                # Home and shell
                create_command.extend(["--no-create-home", "--home-dir", target_home])
                create_command.extend(["--shell", target_shell])

                # Password hash
                if target_password_hash:
                    create_command.extend(["--password", target_password_hash])

                # User's name
                create_command.extend(["--", user])

                # Create user
                conn.run(create_command)
            else:
                # Remove user
                conn.run(["userdel", "--", user])
        elif present:
            # User exists but we need to change some properties
            if op.changed("uid") and target_uid is not None:
                conn.run(["usermod", "--uid", str(target_uid), "--", user])

            if op.changed("group") and target_group is not None:
                conn.run(["usermod", "--gid", target_group, "--", user])

            if op.changed("groups") and len(target_groups) > 0:
                # Empty param for --groups is OK and does the expected thing.
                conn.run(["usermod", "--groups", ','.join(target_groups), "--", user])

            if op.changed("comment") and target_comment is not None:
                conn.run(["usermod", "--comment", target_comment, "--", user])

            if op.changed("home"):
                conn.run(["usermod", "--home", target_home, "--", user])

            if op.changed("shell"):
                conn.run(["usermod", "--shell", target_shell, "--", user])

            if op.changed("password_hash") and target_password_hash is not None:
                conn.run(["usermod", "--password", target_password_hash, "--", user])

    return op.success()

@operation("group")
def group(group: str, # pylint: disable=redefined-outer-name,too-many-statements
          present: bool = True,
          gid: Optional[int] = None,
          system: bool = False,
          name: Optional[str] = None,
          check: bool = True,
          op: Operation = Operation.internal_use_only) -> OperationResult:
    """
    Creates, modifies or deletes a unix group.

    ### Example:

    ```python
    system.group(
        name="Create a new group",
        user="testgroup")
    ```

    Parameters
    ----------
    group
        The name of the group.
    present
        Whether the given group should exists. If False any existing group with that name will be deleted and all other parameters ignored.
    gid
        The gid for the group. Automatically determined if not specified.
    system
        If `True` the group will be created as a system group. This doesn't affect existing groups.
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
    op.desc(group)
    conn = fora.host.current_host.connection

    # Examine current state
    current = conn.query_group(group=group)
    if current is None:
        op.initial_state(exists=False, gid=None)
    else:
        op.initial_state(exists=True, gid=current.gid)

    # Calculate target state. None means no-desired-value (i.e. keep as-is or use default on creation)
    target_gid = gid or (current.gid if current else None)

    if present:
        op.final_state(exists=True, gid=target_gid)
    else:
        op.final_state(exists=False, gid=None)

    # Return success if nothing needs to be changed
    if op.unchanged():
        return op.success()

    # Apply actions to reach desired state, but only if we are not doing a dry run
    if not G.args.dry:
        if op.changed("exists"):
            if present:
                # Create new group
                create_command = ["groupadd"]
                if system:
                    create_command.append("--system")

                if target_gid is not None:
                    create_command.extend(["--gid", str(target_gid)])

                # Group's name
                create_command.extend(["--", group])

                # Create group
                conn.run(create_command)
            else:
                # Remove group
                conn.run(["groupdel", "--", group])
        elif present:
            # Group exists but we need to change some properties
            if op.changed("gid") and target_gid is not None:
                conn.run(["groupmod", "--gid", str(target_gid), "--", group])

    return op.success()

def package(packages: list[str],
            present: bool = True,
            name: Optional[str] = None,
            check: bool = True) -> OperationResult:
    """
    Adds or removes system packages. This operation first detects whether a supported package manager
    is available on the remote system to execute the operation.

    ### Example:

    ```python
    system.package(
        name="Install htop",
        packages=["htop"])

    system.package(
        name="Install neovim and git",
        packages=["neovim", "git"])

    system.package(
        name="Uninstall nano",
        packages=["nano"],
        present=False)
    ```

    Parameters
    ----------
    packages
        The packages to modify.
    present
        Whether the given package should be installed or uninstalled.
    name
        The name for the operation.
    check
        If True, returning `op.failure()` will raise an OperationError. All manually raised
        OperationErrors will be propagated. When False, any manually raised OperationError will
        be caught and `op.failure()` will be returned with the given message while continuing execution.
    """
    # Find package manager module
    conn = fora.host.current_host.connection
    package_fn = find_command(conn, utils.package_managers)
    if package_fn is None:
        raise new_op_fail(op_name="package", name=name, desc=str(packages), error=f"No supported package manager was found on the remote system. Searched commands: {utils.package_managers.keys()}")

    return cast(OperationResult, package_fn(packages=packages, present=present, name=name, check=check))

def service(service: str, # pylint: disable=redefined-outer-name
            state: Optional[str] = None,
            enabled: Optional[bool] = None,
            name: Optional[str] = None,
            check: bool = True) -> OperationResult:
    """
    Manages a system service. This operation first detects whether a supported init system
    is available on the remote system to execute the operation.

    ### Example:

    ```python
    system.service(
        name="Enable sshd to start on boot, and ensure it is started now",
        service="sshd",
        state="started",
        enable=True)

    system.service(
        name="Just enable sshd to start on boot, but don't change anything about its current state",
        service="sshd",
        enable=True)

    system.service(
        name="Restart the nginx service now",
        service="nginx",
        state="restarted")
    ```

    Parameters
    ----------
    service
        The unit to manage.
    state
        The desired state of the unit. Valid options are `started`, `restarted`, `reloaded` and `stopped`.
        If None, the service's current state will not be changed.
    enabled
        Whether the unit should be started on boot.
    name
        The name for the operation.
    check
        If True, returning `op.failure()` will raise an OperationError. All manually raised
        OperationErrors will be propagated. When False, any manually raised OperationError will
        be caught and `op.failure()` will be returned with the given message while continuing execution.
    """
    # Find service manager module
    conn = fora.host.current_host.connection
    service_fn = find_command(conn, utils.service_managers)
    if service_fn is None:
        raise new_op_fail(op_name="service", name=name, desc=str(service), error=f"No supported service manager was found on the remote system. Searched commands: {utils.service_managers.keys()}")

    return cast(OperationResult, service_fn(service=service, state=state, enabled=enabled, name=name, check=check))
