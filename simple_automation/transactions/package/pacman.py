"""
Provides pacman related transactions.
"""

from simple_automation.context import Context
from simple_automation.transactions.basic import _template_str
from simple_automation.transactions.package.utils import generic_package

def is_installed(context: Context, atom: str):
    """
    Queries whether or the given package atom is installed on the remote.
    """
    remote_query = context.remote_exec(["pacman", "-Ql", atom])
    return remote_query.return_code == 0

def package(context: Context, atom: str, state="present", opts: list = None):
    """
    Installs or uninstalls (depending if state == "present" or "absent") the given
    package atom. Additional options to pacman can be passed via opts, and will be appended
    before the package atom. opts will be templated.
    """
    opts = [] if opts is None else [_template_str(context, o) for o in opts]

    def install(context, atom):
        pacman_cmd = ["pacman", "--color", "always", "--noconfirm"]
        pacman_cmd.extend(opts)
        pacman_cmd.append(atom)

        context.remote_exec(pacman_cmd, checked=True)

    def uninstall(context, atom):
        context.remote_exec(["pacman", "--color", "always", "--noconfirm", "-Rs"] + opts + [atom], checked=True)

    generic_package(context, atom, state, is_installed, install, uninstall)
