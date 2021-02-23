"""
Provides apt related transactions.
"""

from simple_automation.context import Context
from simple_automation.transactions.utils import template_str
from simple_automation.transactions.package.utils import generic_package

def is_installed(context: Context, atom: str):
    """
    Queries whether or not the given package atom is installed on the remote.

    Parameters
    ----------
    context : Context
        The context providing the execution context and templating dictionary.
    atom : str
        The package name to query. Will be templated.

    Returns
    -------
    bool
        True if the package is installed
    """
    remote_query = context.remote_exec(["dpgk-query", "--show", "--showformat=${Status}", atom], checked=True)
    return "ok installed" in remote_query.stdout

def package(context: Context, atom: str, state="present", opts: list[str] = None):
    """
    Installs or uninstalls (depending if state == "present" or "absent") the given
    package atom. Additional options to apt-get can be passed via opts, and will be appended
    before the package atom. opts will be templated.

    Parameters
    ----------
    context : Context
        The context providing the execution context and templating dictionary.
    atom : str
        The package name to be installed or uninstalled. Will be templated.
    state : str, optional
        The desired state, either "present" or "absent". Defaults to "present".
    opts : list[str]
        Additional options to pacman. Will be templated.

    Returns
    -------
    CompletedTransaction
        The completed transaction
    """
    opts = [] if opts is None else [template_str(context, o) for o in opts]

    def install(context, atom):
        apt_cmd = ["apt-get", "install"]
        apt_cmd.extend(opts)
        apt_cmd.append(atom)

        context.remote_exec(apt_cmd, checked=True)

    def uninstall(context, atom):
        context.remote_exec(["apt-get", "remove"] + opts + [atom], checked=True)

    generic_package(context, atom, state, is_installed, install, uninstall)
