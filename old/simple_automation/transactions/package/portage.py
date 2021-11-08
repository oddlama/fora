"""
Provides portage related transactions.
"""

from simple_automation.context import Context
from simple_automation.transactions.utils import template_str
from simple_automation.transactions.package.utils import generic_package

ATOMS = ['category', 'name', 'version', 'ebuild_revision', 'slots', 'prefixes', 'sufixes']
INFO_ATOMS = ['version', 'ebuild_revision', 'slots', 'prefixes', 'sufixes']

def list_packages(context: Context):
    """
    Returns a dictionary of all installed packages on the remote system.
    The dictionary maps from "{category}/{name}" → any INFO_ATOMS → str/None

    Parameters
    ----------
    context : Context
        The context providing the execution context and templating dictionary.

    Returns
    -------
    list[str]
        All package atoms that are installed on the remote system.
    """
    # Query installed packages
    remote_packages = context.remote_exec(["sh", "-c", "qlist -CIv | xargs qatom -C --"], checked=True)
    packages = {}

    # Process each atom
    for p in remote_packages.stdout.splitlines():
        tokens = p.split()
        category, name = tokens[:2]
        info = dict(zip(INFO_ATOMS, tokens[2:]))

        # Make info total
        for a in INFO_ATOMS:
            if a not in info or info[a] == "<unset>":
                info[a] = None

        # Save package info
        cn = f"{category}/{name}"
        packages[cn] = info

    return packages

def is_installed(context: Context, atom: str, packages: list[str] = None):
    """
    Queries whether or not the given package atom is installed on the remote.

    Parameters
    ----------
    context : Context
        The context providing the execution context and templating dictionary.
    atom : str
        The package name to query. Will be templated.
    packages : list[str]
        Additional options to portage. Will be templated.

    Returns
    -------
    bool
        True if the package is installed
    """
    remote_atom = context.remote_exec(["qatom", "-C", "--", atom], checked=True)
    package_info = dict(zip(ATOMS, remote_atom.stdout.split()))
    cn = f"{package_info['category']}/{package_info['name']}"

    # Query packages if not given
    if packages is None:
        packages = list_packages(context)
    return cn in packages

def package(context: Context, atom: str, state="present", oneshot=False, opts: list[str] = None):
    """
    Installs or uninstalls the given package atom (depending on state == "present" or "absent").
    Additional options to emerge can be passed via opts, and will be appended
    before the package atom. opts will be templated.

    Parameters
    ----------
    context : Context
        The context providing the execution context and templating dictionary.
    atom : str
        The package name to be installed or uninstalled. Will be templated.
    state : str, optional
        The desired state, either "present" or "absent". Defaults to "present".
    oneshot : bool, optional
        Use portage option --oneshot. Defaults to false.
    opts : list[str]
        Additional options to portage. Will be templated.

    Returns
    -------
    CompletedTransaction
        The completed transaction
    """
    opts = [] if opts is None else [template_str(context, o) for o in opts]

    def install(context, atom):
        emerge_cmd = ["emerge", "--color=y", "--verbose"]
        if oneshot:
            emerge_cmd.append("--oneshot")
        emerge_cmd.extend(opts)
        emerge_cmd.append(atom)

        context.remote_exec(emerge_cmd, checked=True)

    def uninstall(context, atom):
        context.remote_exec(["emerge", "--color=y", "--verbose", "--depclean"] + opts + [atom], checked=True)

    generic_package(context, atom, state, is_installed, install, uninstall)
