"""
Provides apt related transactions.
"""

from simple_automation.context import Context
from simple_automation.transactions.utils import template_str
from simple_automation.transactions.package.utils import generic_package

def is_installed(context: Context, name: str):
    """
    Queries whether or not the given package name is installed on the remote.

    Parameters
    ----------
    context : Context
        The context providing the execution context and templating dictionary.
    name : str
        The package name to query. Will be templated.

    Returns
    -------
    bool
        True if the package is installed
    """
    remote_query = context.remote_exec(["dpgk-query", "--show", "--showformat=${Status}", name], checked=True)
    return "ok installed" in remote_query.stdout

def package(context: Context, name: str, state="present", opts: list[str] = None):
    """
    Installs or uninstalls the given package name (depending on state == "present" or "absent").
    Additional options to apt-get can be passed via opts, and will be appended
    before the package name. opts will be templated.

    Parameters
    ----------
    context : Context
        The context providing the execution context and templating dictionary.
    name : str
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

    def install(context, name):
        apt_cmd = ["apt-get", "install"]
        apt_cmd.extend(opts)
        apt_cmd.append(name)

        context.remote_exec(apt_cmd, checked=True)

    def uninstall(context, name):
        context.remote_exec(["apt-get", "remove"] + opts + [name], checked=True)

    generic_package(context, name, state, is_installed, install, uninstall)
