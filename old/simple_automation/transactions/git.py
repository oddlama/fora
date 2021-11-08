"""
Provides git related transactions.
"""

from simple_automation.checks import check_valid_path
from simple_automation.context import Context
from simple_automation.exceptions import LogicError, RemoteExecError
from simple_automation.transactions.utils import template_str, remote_stat

def clone(context: Context, url: str, dst: str, depth=None):
    """
    Clone a git repository, without updating it, if it is already cloned. Same as calling
    :func:`~checkout()` with update=False.

    Parameters
    ----------
    context : Context
        The context providing the execution context and templating dictionary.
    url : str
        The url of the git repository to checkout. Will be templated.
    dst : str
        The remote destination path for the repository. Will be templated.
    depth : str, optional
        Restrict repository cloning depth. Beware that updates might not work correctly because of forced updates.

    Returns
    -------
    CompletedTransaction
        The completed transaction
    """
    return checkout(context, url, dst, update=False, depth=depth)

def checkout(context: Context, url: str, dst: str, update: bool = True, depth=None):
    """
    Checkout (and optionally update) the given git repository to dst.

    Parameters
    ----------
    context : Context
        The context providing the execution context and templating dictionary.
    url : str
        The url of the git repository to checkout. Will be templated.
    dst : str
        The remote destination path for the repository. Will be templated.
    update: bool, optional
        Also tries to update the repository if it is already cloned. Defaults to true.
    depth : str, optional
        Restrict repository cloning depth. Beware that updates might not work correctly because of forced updates.

    Returns
    -------
    CompletedTransaction
        The completed transaction
    """
    url = template_str(context, url)
    dst = template_str(context, dst)
    check_valid_path(dst)

    with context.transaction(title="checkout", name=dst) as action:
        # Add url as extra info
        action.extra_info(url=url)

        # Query current state
        (cur_ft, _, _, _) = remote_stat(context, dst)

        # Record this initial state
        if cur_ft is None:
            action.initial_state(cloned=False, commit=None)
            cloned = False
        elif cur_ft == "directory":
            # Assert that it is a git directory
            (cur_git_ft, _, _, _) = remote_stat(context, dst + "/.git")
            if cur_git_ft != 'directory':
                raise LogicError("Cannot checkout git repository on remote: Directory already exists and is not a git repository")

            remote_commit = context.remote_exec(["git", "-C", dst, "rev-parse", "HEAD"], error_verbosity=0, verbosity=2)
            if remote_commit.return_code != 0:
                raise LogicError("Cannot checkout git repository on remote: Directory already exists but 'git rev-parse HEAD' failed")

            cur_commit = remote_commit.stdout.strip()
            action.initial_state(cloned=True, commit=cur_commit)
            cloned = True
        else:
            raise LogicError("Cannot checkout git repository on remote: Path already exists but isn't a directory")

        # If the repository is already cloned but we shouldn't update,
        # nothing will change and we are done.
        if cloned and not update:
            return action.unchanged()

        # Check the newest available commit
        remote_newest_commit = context.remote_exec(["git", "ls-remote", "--exit-code", url, "HEAD"], checked=True)
        newest_commit = remote_newest_commit.stdout.strip().split()[0]

        # Record the final state
        action.final_state(cloned=True, commit=newest_commit)

        # Apply actions to reach new state, if we aren't in pretend mode
        if not context.pretend:
            try:
                if not cloned:
                    clone_cmd = ["git", "clone"]
                    if depth is not None:
                        clone_cmd.append("--depth")
                        clone_cmd.append(str(depth))
                    clone_cmd.append(url)
                    clone_cmd.append(dst)

                    context.remote_exec(clone_cmd, checked=True)
                else:
                    pull_cmd = ["git", "-C", dst, "pull", "--ff-only"]
                    if depth is not None:
                        pull_cmd.append("--depth")
                        pull_cmd.append(str(depth))
                    context.remote_exec(pull_cmd, checked=True)
            except RemoteExecError as e:
                return action.failure(e)

        # Return success
        return action.success()
