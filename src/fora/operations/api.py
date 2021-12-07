"""Provides API to define operations."""

import shutil
import subprocess
import sys

from functools import wraps
from typing import Callable, cast, Any, Optional
from types import TracebackType, FrameType

import fora.script
from fora import globals as G, logger
from fora.script import RemoteDefaultsContext

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

    def __init__(self, op_name: str, name: Optional[str]):
        self.op_name = op_name
        self.name = name
        self.has_nested = False
        self.description: str = "?"
        self.initial_state_dict: Optional[dict[str, Any]] = None
        self.final_state_dict: Optional[dict[str, Any]] = None
        self.diffs: list[tuple[str, Optional[bytes], Optional[bytes]]] = []

    def nested(self, has_nested: bool) -> None:
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

    def add_nested_result(self, key: str, result: OperationResult) -> None:
        """
        Adds initial and final state of a nested operation under the given key
        into this operation's state dictionaries.

        Parameters
        ----------
        key
            The key under which to add the nested result.
        result
            The result to add.
        """
        if not self.has_nested:
            raise OperationError("An operation can only accumulate nested results if it is marked as nested.")
        if self.initial_state_dict is None:
            self.initial_state_dict = {}
        if self.final_state_dict is None:
            self.final_state_dict = {}
        if key in self.initial_state_dict or key in self.final_state_dict:
            raise OperationError(f"Cannot add nested operation result under existing key '{key}'.")
        self.initial_state_dict[key] = result.initial
        self.final_state_dict[key] = result.final

    def desc(self, description: str) -> None:
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

    def defaults(self, *args: Any, **kwargs: Any) -> RemoteDefaultsContext:
        """Sets defaults on the current script. See `fora.types.ScriptType.defaults`."""
        _ = (self)
        return fora.script.defaults(*args, **kwargs)

    def initial_state(self, **kwargs: Any) -> None:
        """Sets the initial state."""
        if self.has_nested:
            raise OperationError("An operation that nests other operations cannot have state on its own.")
        if self.initial_state_dict is not None:
            raise OperationError("An operation's 'initial_state' can only be set once.")
        self.initial_state_dict = dict(kwargs)

    def final_state(self, **kwargs: Any) -> None:
        """Sets the final state."""
        if self.has_nested:
            raise OperationError("An operation that nests other operations cannot have state on its own.")
        if self.final_state_dict is not None:
            raise OperationError("An operation's 'final_state' can only be set once.")
        self.final_state_dict = dict(kwargs)

    def unchanged(self, ignore_none: bool = False) -> bool:
        """
        Checks whether the initial and final states differ.

        Parameters
        ----------
        ignore_none
            Set to `True` to not count states where the final value is None.

        Returns
        -------
        bool
            Whether the states differ.
        """
        if self.initial_state_dict is None or self.final_state_dict is None:
            raise OperationError("Both initial and final state must have been set before 'unchanged()' may be called.")

        if not ignore_none:
            return self.initial_state_dict == self.final_state_dict

        keys_not_none = (k for k in self.final_state_dict if k is not None)
        for k in keys_not_none:
            if self.initial_state_dict[k] != self.final_state_dict[k]:
                return False
        return True


    def changed(self, key: str) -> bool:
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
        return bool(self.initial_state_dict[key] != self.final_state_dict[key])

    def diff(self, file: str, old: Optional[bytes], new: Optional[bytes]) -> None:
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
        if old == new:
            return
        self.diffs.append((file, old, new))

    def failure(self, msg: str) -> OperationResult:
        """
        Returns a failed operation result.

        Returns
        -------
        OperationResult
            The OperationResult for this failed operation.
        """
        result = OperationResult(success=False,
                changed=False,
                initial=self.initial_state_dict or {},
                final=self.final_state_dict or {},
                failure_message=msg)
        if not self.has_nested:
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
        if self.initial_state_dict is None or self.final_state_dict is None:
            raise OperationError("Both initial and final state must have been set before 'success()' may be called.")
        result = OperationResult(success=True,
                changed=not self.unchanged(),
                initial=self.initial_state_dict,
                final=self.final_state_dict)
        if not self.has_nested:
            logger.print_operation(self, result)
        return result

def operation(op_name: str) -> Callable[[Callable], Callable]:
    """Operation function decorator."""

    def _calling_site_traceback() -> TracebackType:
        """
        Returns a modified traceback object which can be used in Exception.with_traceback() to make
        the exception appear as if it originated at the calling site of the operation.
        """
        try:
            raise AssertionError
        except AssertionError:
            traceback = sys.exc_info()[2]
            if traceback is None:
                raise RuntimeError("Traceback cannot be None. This is a bug!") from None
            back_frame: Optional[FrameType] = traceback.tb_frame
            back_frame = back_frame.f_back if back_frame else None # Omit this function
            back_frame = back_frame.f_back if back_frame else None # Omit the function where _calling_site_traceback is called (the operation_wrapper below)
            if back_frame is None:
                raise RuntimeError("back_frame cannot be None. This is a bug!") from None

        return TracebackType(tb_next=None,
                             tb_frame=back_frame,
                             tb_lasti=back_frame.f_lasti,
                             tb_lineno=back_frame.f_lineno)

    def operation_wrapper(function: Callable) -> Callable:
        @wraps(function)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            op = Operation(op_name=op_name, name=kwargs.get("name", None))
            check = kwargs.get("check", True)

            try:
                ret = function(*args, **kwargs, op=op)
            except OperationError as e:
                ret = op.failure(str(e))
                # If we are not in debug mode, we modify the traceback such that the exception
                # seems to originate at the calling site where the operation is called.
                if G.args.debug:
                    raise
                raise e.with_traceback(_calling_site_traceback())
            except subprocess.CalledProcessError as e:
                ret = op.failure(str(e))
                cols = max(shutil.get_terminal_size((80, 20)).columns, 80)

                def print_fullwith(msg: list[str], pad: str = '─') -> None:
                    """Prints a message padded to the terminal width to stderr."""
                    msglen = sum(map(lambda s: 0 if s.startswith("\033[") else len(s), msg))
                    print(pad * 8 + ''.join(msg) + pad * (cols - msglen - 8), file=sys.stderr)

                # Print output of failed command for debugging
                col_red = logger.col("\033[1;31m")
                col_reset = logger.col("\033[m")
                print_fullwith(["────────[ ",
                    col_red, "command", col_reset, " ",
                    str(e.cmd),
                    col_red, "failed", col_reset, " ",
                    f"with code {e.returncode} ]"])
                print_fullwith(["────────[ ", col_red, "stdout", col_reset, " (special characters escaped) ]"])
                print(e.stdout.decode("utf-8", errors="backslashreplace"), file=sys.stderr)
                print_fullwith(["────────[ ", col_red, "stderr", col_reset, " (special characters escaped) ]"])
                print(e.stderr.decode("utf-8", errors="backslashreplace"), file=sys.stderr)

                if G.args.debug:
                    raise
                raise e.with_traceback(_calling_site_traceback())
            except Exception as e:
                ret = op.failure(str(e))
                raise

            if ret is None:
                raise OperationError("The operation failed to return a status. THIS IS A BUG! Please report it to the package maintainer of the package which the operation belongs to.")

            if check and not ret.success:
                error = OperationError(ret.failure_message)
                # If we are not in debug mode, we modify the traceback such that the exception
                # seems to originate at the calling site where the operation is called.
                if G.args.debug:
                    raise error
                raise error.with_traceback(_calling_site_traceback())

            return ret
        return wrapper
    return operation_wrapper
