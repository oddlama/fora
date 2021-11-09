"""
Provides necessary components to define operations.
"""

import sys

from functools import wraps
from typing import cast, Any, Optional
from types import TracebackType, FrameType

import simple_automation
from simple_automation import logger
from simple_automation.types import RemoteDefaultsContext, ScriptType

class OperationError(Exception):
    """An exception that indicates an error while executing an operation."""

class OperationResult:
    """Stores the result of an operation."""

    def __init__(self,
                 success: bool,
                 changed: bool,
                 initial: dict[str, Any],
                 final: dict[str, Any],
                 failure_message: Optional[str] = None):
        self.success = success
        self.changed = changed
        self.initial = initial
        self.final = final
        self.failure_message = failure_message

class Operation:
    """This class is used to ease the building of operations with consistent output and state tracking."""

    internal_use_only: "Operation" = cast("Operation", None)
    """operation's op variable is defaulted to this value to indicate that it must not be given by the user."""

    def __init__(self, op_name: str, name: str):
        self.op_name = op_name
        self.name = name
        self.has_nested = False
        self.description: str
        self.initial_state_dict: Optional[dict[str, Any]] = None
        self.final_state_dict: Optional[dict[str, Any]] = None
        self.diffs: list[tuple[str, Optional[bytes], Optional[bytes]]] = []

    def nested(self, has_nested: bool):
        """
        Sets whet this operation spawns nested operations. In this case,
        this operation will not have separate state, and the printing will be
        handled differently.

        Parameters
        ----------
        has_nested
            Whether the operation has nested operations.
        """
        self.has_nested = has_nested

    def desc(self, description: str):
        """
        Sets the description of the operation, and prints an
        early status via the logger.

        Parameters
        ----------
        description
            The new description.
        """
        self.description = description
        logger.print_operation_early(self)
        if self.has_nested:
            print()

    def defaults(self, *args, **kwargs) -> RemoteDefaultsContext:
        """
        Sets defaults on the current script. See :meth:`simple_automation.types.ScriptType.defaults`.
        """
        _ = (self)
        return cast(ScriptType, simple_automation.this).defaults(*args, **kwargs)

    def initial_state(self, **kwargs):
        """
        Sets the initial state.
        """
        if self.has_nested:
            raise OperationError("An operation that nests other operations cannot have state on its own.")
        if self.initial_state_dict is not None:
            raise OperationError("An operation's 'initial_state' can only be set once.")
        self.initial_state_dict = dict(kwargs)

    def final_state(self, **kwargs):
        """
        Sets the final state.
        """
        if self.has_nested:
            raise OperationError("An operation that nests other operations cannot have state on its own.")
        if self.final_state_dict is not None:
            raise OperationError("An operation's 'final_state' can only be set once.")
        self.final_state_dict = dict(kwargs)

    def unchanged(self) -> bool:
        """
        Checks whether the initial and final states differ.

        Returns
        -------
        bool
            Whether the states differ.
        """
        if self.has_nested:
            raise OperationError("An operation that nests other operations cannot have state on its own.")
        if self.initial_state_dict is None or self.final_state_dict is None:
            raise OperationError("Both initial and final state must have been set before 'unchanged()' may be called.")
        return self.initial_state_dict == self.final_state_dict

    def changed(self, key):
        """
        Checks whether a specific key will change.

        Parameters
        ----------
        key
            The key to check for changes.

        Returns
        -------
        bool
            Whether the states differ.
        """
        if self.has_nested:
            raise OperationError("An operation that nests other operations cannot have state on its own.")
        if self.initial_state_dict is None or self.final_state_dict is None:
            raise OperationError("Both initial and final state must have been set before 'changed()' may be called.")
        return self.initial_state_dict[key] != self.final_state_dict[key]

    def diff(self, file: str, old: Optional[bytes], new: Optional[bytes]):
        """
        Adds a file to the diffing output.

        Parameters
        ----------
        file
            The filename which the diff belongs to.
        old
            The previous content or None if the file didn't exist previously.
        new
            The new content or None if the file was deleted.
        """
        if self.has_nested:
            raise OperationError("An operation that nests other operations cannot have state on its own.")
        self.diffs.append((file, old, new))

    def failure(self, msg: str) -> OperationResult:
        """
        Returns a failed operation result.

        Returns
        -------
        OperationResult
            The OperationResult for this failed operation.
        """
        if self.has_nested:
            raise OperationError("An operation that nests other operations cannot have state on its own.")
        result = OperationResult(success=False,
                changed=False,
                initial=self.initial_state_dict or {},
                final={},
                failure_message=msg)
        logger.print_operation(self, result)
        return result

    def success(self) -> OperationResult:
        """
        Returns a successful operation result.

        Returns
        -------
        OperationResult
            The OperationResult for this successful operation.
        """
        if self.has_nested:
            raise OperationError("An operation that nests other operations cannot have state on its own.")
        if self.initial_state_dict is None or self.final_state_dict is None:
            raise OperationError("Both initial and final state must have been set before 'success()' may be called.")
        result = OperationResult(success=True,
                changed=self.initial_state_dict != self.final_state_dict,
                initial=self.initial_state_dict,
                final=self.final_state_dict)
        logger.print_operation(self, result)
        return result

def operation(op_name):
    """Operation function decorator."""
    def _calling_site_traceback() -> TracebackType:
        """
        Returns a modified traceback object which can be used in Exception.with_traceback() to make
        the exception appear as if it originated at the calling site of the operation.
        """
        try:
            raise AssertionError
        except AssertionError:
            traceback = cast(TracebackType, sys.exc_info()[2])
            back_frame = cast(FrameType, traceback.tb_frame)
            back_frame = cast(FrameType, back_frame.f_back) # Omit this function
            back_frame = cast(FrameType, back_frame.f_back) # Omit the function where _calling_site_traceback is called (the operation_wrapper below)

        return TracebackType(tb_next=None,
                             tb_frame=back_frame,
                             tb_lasti=back_frame.f_lasti,
                             tb_lineno=back_frame.f_lineno)

    def operation_wrapper(function):
        @wraps(function)
        def wrapper(*args, **kwargs):
            op = Operation(op_name=op_name, name=kwargs.get("name", None))
            check = kwargs.get("check", True)

            try:
                ret = function(*args, **kwargs, op=op)
            except OperationError as e:
                ret = op.failure(str(e))
                if check:
                    # If we are not in debug mode, we modify the traceback such that the exception
                    # seems to originate at the calling site where the operation is called.
                    if simple_automation.args.debug:
                        raise
                    raise e.with_traceback(_calling_site_traceback())
            except Exception as e:
                ret = op.failure(str(e))
                raise

            if ret is None:
                raise OperationError("The operation failed to return a status. THIS IS A BUG! Please report it to the package maintainer of the package which the operation belongs to.")

            if check and not ret.success:
                e = OperationError(ret.failure_message)
                # If we are not in debug mode, we modify the traceback such that the exception
                # seems to originate at the calling site where the operation is called.
                if simple_automation.args.debug:
                    raise e
                raise e.with_traceback(_calling_site_traceback())

            return ret
        return wrapper
    return operation_wrapper
