"""Provides operations related to the operating system such as user, group or service management."""

from typing import Optional

from fora import globals as G
import fora.host
from fora.operations.api import Operation, OperationResult, operation

@operation("user")
def user(user: str, # pylint: disable=redefined-outer-name,too-many-statements
         present: bool = True,
         uid: Optional[int] = None,
         group: Optional[str] = None,
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

    Parameters
    ----------
    user
        The name of the user.
    present
        Whether the given user should exists. If False any existing user will be deleted and other parameters ignored.
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
        The password hash for the user as given by `crypt(3)`. Use `"!"` to lock the account.
        You can generate a password hash by using the following code:

            import crypt, getpass
            real_pw = getpass.getpass()
            password_hash = crypt.crypt(real_pw, crypt.mksalt(crypt.METHOD_SHA512))

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

    # Examine current state
    current = conn.query_user(user=user)
    if current is None:
        op.initial_state(exists=False, uid=None, group=None, groups=None, comment=None, home=None, shell=None, password_hash=None)
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
    target_home = home or (current.home if current else None)
    target_shell = shell or (current.shell if current else '/sbin/nologin')

    if present:
        op.final_state(exists=True, uid=target_uid, group=target_group, groups=target_groups, comment=target_comment, home=target_home, shell=target_shell, password_hash=target_password_hash)
    else:
        op.final_state(exists=False, uid=None, group=None, groups=None, comment=None, home=None, shell=None, password_hash=None)

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
                create_command.extend(["--no-create-home", "--home-dir", target_home or '/dev/null'])
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

            if op.changed("groups"):
                # Empty param for --groups is OK and does the expected thing.
                conn.run(["usermod", "--groups", ','.join(target_groups), "--", user])

            if op.changed("comment") and target_comment is not None:
                conn.run(["usermod", "--comment", target_comment, "--", user])

            if op.changed("home") and target_home is not None:
                conn.run(["usermod", "--home", target_home, "--", user])

            if op.changed("shell"):
                conn.run(["usermod", "--shell", target_shell, "--", user])

            if op.changed("password_hash") and target_password_hash is not None:
                conn.run(["usermod", "--password", target_password_hash, "--", user])

    return op.success()
