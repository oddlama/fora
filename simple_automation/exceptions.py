class SimpleAutomationError(Exception):
    pass

class LogicError(SimpleAutomationError):
    pass

class RemoteExecError(SimpleAutomationError):
    pass
