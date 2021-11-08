"""
Provides exception types for simple_automation.
"""

class SimpleAutomationError(Exception):
    """
    Base exception class for simple_automation errors.
    """

class MessageError(SimpleAutomationError):
    """
    An error type for which only the message will be printed, and the stacktrace supressed.
    """

class LogicError(SimpleAutomationError):
    """
    Exception class for logic (i.e. "compile time") errors.
    """

class RemoteExecError(SimpleAutomationError):
    """
    Exception class for remote execution errors.
    """

    def __init__(self, command, ret):
        """
        Initializes the exception object and stores additional information about the error context.
        """
        super().__init__(f"Remote command {command} was unsuccessful (code {ret.return_code})")
        self.command = command
        self.ret = ret

class TransactionError(MessageError):
    """
    Exception class for transaction errors.
    """
    def __init__(self, result):
        """
        Initializes the exception object and stores additional information about the error context.
        """
        super().__init__(result.failure_reason)
        self.result = result
