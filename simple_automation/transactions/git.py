from simple_automation import Context
from simple_automation.checks import check_valid_dir
from simple_automation.transactions.basic import _template_str

def checkout(context: Context, url: str, dst: str, update: bool = False, depth=None):
    url = _template_str(context, url)
    dst = _template_str(context, dst)
    check_valid_dir(dst)

    with context.transaction(title="checkout", name=dst) as action:
        # Query current state
        # Record this initial state
        action.extra_info(url=url)
        action.initial_state(commit=False)

        # Record the final state
        action.final_state(commit="aaaa")
        # Apply actions to reach new state, if we aren't in pretend mode
        if not context.pretend:
            pass

        # Return success
        return action.success()
