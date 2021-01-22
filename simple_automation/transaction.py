from simple_automation.exceptions import LogicError

class CompletedTransaction:
    """
    A CompletedTransaction is a manifest of the initial and final state of an transition.
    Additionally, it records a success status, a changed flag to indicate that at least one
    action has actually been performed, as well as additional stored values
    defined by the specific transaction for later use.
    """
    def __init__(self, transaction, success, store, failure_reason=None):
        self.success = success
        self.failure_reason = failure_reason
        self.initial_state = transaction.initial_state_dict
        self.final_state = transaction.final_state_dict
        self.changed = (self.initial_state == self.final_state)

        # Set additional return variables
        # TODO for k,v in ...:
        # TODO     setvar(k, v)

class Transaction:
    """
    A wrapper around a transaction context that enforces usage of the
    'with' statement to modify the transaction.
    """
    def __init__(self, context):
        self.context = context

    def __enter__(self):
        """
        Begins a new transaction
        """
        if self.transaction_context is not None:
            raise LogicError("A transaction may only be started once.")
        self.transaction_context = ActiveTransaction()
        return self.transaction_context

    def __exit__(self, exc_type, exc_value, trace):
        """
        Finalizes the transaction and logs its status.
        """
        self.transaction_context.finalize()

class ActiveTransaction:
    """
    Represents a transaction on a remote host. Transactions are operational units,
    which alter the state of a remote from an initial state A to a known target state.
    When they begin, they must examine the initial state, and transition the remote
    into the target state. This possible state change will be presented to the user.
    """
    def __init__(self):
        self.initial_state_dict = None
        self.final_state_dict = None
        self.result = None

    def finalize(self, context):
        if self.initial_state_dict is None:
            raise LogicError("A transaction cannot be completed without an initial state.")
        if self.final_state_dict is None:
            raise LogicError("A transaction cannot be completed without a final state.")
        if self.result is None:
            raise LogicError("A transaction cannot be completed without a result status.")
        # TODO Ensure all required states are set
        # TODO Log differences
        pass

    def initial_state(self, **kwargs):
        """
        Records the observed initial state of the remote.
        """
        if self.result is not None:
            raise LogicError("A transaction cannot be altered after it is completed")
        self.initial_state_dict = dict(kwargs)

    def final_state(self, **kwargs):
        """
        Records the (expected) final state of the remote.
        """
        if self.result is not None:
            raise LogicError("A transaction cannot be altered after it is completed")
        self.final_state_dict = dict(kwargs)

    def success(self, **kwargs):
        """
        Completes the transaction with successful status.
        """
        if self.result is not None:
            raise LogicError("A transaction cannot be completed multiple times.")
        self.result = CompletedTransaction(self, success=True, store=kwargs)
        return self.result

    def failure(self, reason, **kwargs):
        """
        Completes the transaction, marking it as failed with the given reason.
        """
        if self.result is not None:
            raise LogicError("A transaction cannot be completed multiple times.")
        self.result = CompletedTransaction(self, success=False, failure_reason=reason, store=kwargs)
        return self.result
