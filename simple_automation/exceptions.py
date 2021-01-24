class SimpleAutomationError(Exception):
    pass

class LogicError(SimpleAutomationError):
    pass

class RemoteExecError(SimpleAutomationError):
    pass

class TransactionError(SimpleAutomationError):
    def __init__(self, result):
        super().__init__(result.failure_reason)
        self.result = result
