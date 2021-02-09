class SimpleAutomationError(Exception):
    pass

class MessageError(SimpleAutomationError):
    """
    Stacktrace will be supressed.
    """
    pass

class LogicError(SimpleAutomationError):
    pass

class RemoteExecError(SimpleAutomationError):
    def __init__(self, command, ret):
        super().__init__(f"Remote command {command} was unsuccessful (code {ret.return_code})")
        self.command = command
        self.ret = ret

class TransactionError(MessageError):
    def __init__(self, result):
        super().__init__(result.failure_reason)
        self.result = result
