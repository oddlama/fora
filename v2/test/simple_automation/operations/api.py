"""
Provides necessary components to define operations.
"""

from typing import cast, Union, Any, Optional

import simple_automation
from simple_automation.connection import Connection
from simple_automation.types import RemoteDefaultsContext, HostType, ScriptType, TaskType
from simple_automation.utils import AbortExecutionSignal

class OperationError(Exception):
    """
    An exception that indicates an error while executing an operation.
    """

class OperationResult:
    """
    Stores the result of an operation.
    """

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
    """
    This class is used to ease the building of operations with consistent output and state tracking.
    """

    def __init__(self, op_name: str, name: str):
        self.op_name = op_name
        self.name = name
        self.initial_state_dict: Optional[dict[str, Any]] = None
        self.final_state_dict: Optional[dict[str, Any]] = None
        print(f"{self.op_name=} {self.name=}")

    def connection(self) -> Connection:
        """
        A wrapper to get the current host without mypy complaining.

        Returns
        -------
        Connection
            The connection on which the operation is operating.
        """
        _ = (self)
        return cast(Connection, cast(HostType, simple_automation.host).connection)

    def defaults(self, *args, **kwargs) -> RemoteDefaultsContext:
        """
        Sets defaults on the current script or task. See :meth:`simple_automation.types.ScriptType.defaults`.
        """
        _ = (self)
        return cast(Union[ScriptType, TaskType], simple_automation.this).defaults(*args, **kwargs)

    def initial_state(self, **kwargs):
        """
        Sets the initial state.
        """
        if self.initial_state_dict is not None:
            raise OperationError("An operation's 'initial_state' can only be set once.")
        self.initial_state_dict = dict(kwargs)

        print(f"initial {self.op_name=} {self.name=} {self.initial_state_dict}")

    def final_state(self, **kwargs):
        """
        Sets the final state.
        """
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
        if self.initial_state_dict is None or self.final_state_dict is None:
            raise OperationError("Both initial and final state must have been set before 'changed()' may be called.")
        return self.initial_state_dict[key] != self.final_state_dict[key]

    def failure(self, msg: str) -> OperationResult:
        """
        Returns a failed operation result.

        Returns
        -------
        OperationResult
            The OperationResult for this failed operation.
        """
        # TODO print
        return OperationResult(success=False,
                changed=False,
                initial=self.initial_state_dict or {},
                final={},
                failure_message=msg)

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
        # TODO print
        return OperationResult(success=True,
                changed=self.initial_state_dict != self.final_state_dict,
                initial=self.initial_state_dict,
                final=self.final_state_dict)

def operation(op_name):
    """
    Operation function decorator.
    """
    def operation_wrapper(function):
        def wrapper(*args, **kwargs):
            op = Operation(op_name=op_name, name=kwargs.pop("name", None))
            check = kwargs.pop("check", False)
            try:
                ret = function(*args, **kwargs, op=op)
            except Exception as e:
                # TODO log traceback, return failed
                print(e)
                ret = op.failure(str(e))
                import traceback
                traceback.print_exc()
                raise AbortExecutionSignal() from e

            return ret
        return wrapper
    return operation_wrapper
