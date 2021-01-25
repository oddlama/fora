from simple_automation import Context
from simple_automation.transactions.basic import _template_str


def package(context: Context, atom: str, state="present", oneshot=False):
    atom = _template_str(context, atom)

    with context.transaction(title="package", name=atom) as action:
        # Query current state
        # Record this initial state
        action.initial_state(installed=False)

        # Record the final state
        action.final_state(installed=True)
        # Apply actions to reach new state, if we aren't in pretend mode
        if not context.pretend:
            pass

        # Return success
        return action.success()
