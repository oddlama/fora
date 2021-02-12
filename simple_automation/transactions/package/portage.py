"""
Provides portage related transactions.
"""

from simple_automation.context import Context
from simple_automation.transactions.basic import _template_str
from simple_automation.transactions.package.utils import generic_package

ATOMS = ['category', 'name', 'version', 'ebuild_revision', 'slots', 'prefixes', 'sufixes']
INFO_ATOMS = ['version', 'ebuild_revision', 'slots', 'prefixes', 'sufixes']

def list_packages(context: Context):
    """
    Returns a dictionary of all installed packages on the remote system.
    The dictionary maps from "{category}/{name}" → any INFO_ATOMS → str/None
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

def is_installed(context: Context, atom: str, packages=None):
    """
    Queries whether or the given package atom is installed on the remote.
    """
    remote_atom = context.remote_exec(["qatom", "-C", "--", atom], checked=True)
    package_info = dict(zip(ATOMS, remote_atom.stdout.split()))
    cn = f"{package_info['category']}/{package_info['name']}"

    # Query packages if not given
    if packages is None:
        packages = list_packages(context)
    return cn in packages

def package(context: Context, atom: str, state="present", oneshot=False, opts: list = None):
    """
    Installs or uninstalls (depending if state == "present" or "absent") the given
    package atom. Additional options to emerge can be passed via opts, and will be appended
    before the package atom. opts will be templated.
    """
    opts = [] if opts is None else [_template_str(context, o) for o in opts]

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
