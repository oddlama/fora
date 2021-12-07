"""Provides operations related to the portage package manager."""

from typing import Optional, Union
import fora.host
from fora.operations.api import Operation, OperationResult, operation
from fora.operations.utils import package_manager

@package_manager(command="emerge")
@operation("package")
def package(package: Union[str, list[str]], # pylint: disable=redefined-outer-name,too-many-statements
            present: bool = True,
            name: Optional[str] = None,
            check: bool = True,
            op: Operation = Operation.internal_use_only) -> OperationResult:
    """
    TODO

    Parameters
    ----------
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
    op.desc(str(package))

    conn = fora.host.current_host.connection
    return op.success()
