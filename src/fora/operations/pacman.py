"""Provides operations related to the pacman package manager."""

from functools import partial
from typing import Optional
import fora.host
from fora.operations.api import Operation, OperationResult, operation
from fora.operations.utils import generic_package, package_manager

def _is_installed(package: str, opts: Optional[list[str]] = None) -> bool: # pylint: disable=redefined-outer-name
    """Checks whether a package is installed with pacman on the remote host."""
    opts = opts or []
    return fora.host.current_host.connection.run(["pacman", "-Ql"] + opts + ["--", package], check=False).returncode == 0

def _install(package: str, opts: Optional[list[str]] = None) -> None: # pylint: disable=redefined-outer-name
    """Installs a package with pacman on the remote host."""
    opts = opts or []
    fora.host.current_host.connection.run(["pacman", "--color", "always", "--noconfirm", "-S"] + opts + ["--", package])

def _uninstall(package: str, opts: Optional[list[str]] = None) -> None: # pylint: disable=redefined-outer-name
    """Uninstalls a package with pacman on the remote host."""
    opts = opts or []
    fora.host.current_host.connection.run(["pacman", "--color", "always", "--noconfirm", "-Rns"] + opts + ["--", package])

@package_manager(command="pacman")
@operation("package")
def package(packages: list[str],
            present: bool = True,
            opts: Optional[list[str]] = None,
            name: Optional[str] = None,
            check: bool = True,
            op: Operation = Operation.internal_use_only) -> OperationResult:
    """
    Adds or removes system packages with pacman.

    Parameters
    ----------
    packages
        The packages to modify.
    present
        Whether the given package should be installed or uninstalled.
    opts
        Extra options passed to pacman when installing/uninstalling.
    name
        The name for the operation.
    check
        If True, returning `op.failure()` will raise an OperationError. All manually raised
        OperationErrors will be propagated. When False, any manually raised OperationError will
        be caught and `op.failure()` will be returned with the given message while continuing execution.
    op
        The operation wrapper. Must not be supplied by the user.
    """
    _ = (name, check) # Processed automatically.
    op.desc(str(packages))

    return generic_package(op, packages,
            present=present,
            is_installed=_is_installed,
            install=partial(_install, opts=opts),
            uninstall=partial(_uninstall, opts=opts))
