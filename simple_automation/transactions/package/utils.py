"""
Provides package related utils.
"""

from simple_automation.context import Context
from simple_automation.exceptions import LogicError
from simple_automation.transactions.basic import _template_str

def generic_package(context: Context, atom: str, state, is_installed, install, uninstall):
    """
    Installs or uninstalls (depending if state == "present" or "absent") the given
    package atom. Additional options to emerge can be passed via opts, and will be appended
    before the package atom. opts will be templated.
    """
    # pylint: disable=R0801
    if state not in ["present", "absent"]:
        raise LogicError(f"Invalid package state '{state}'")

    atom = _template_str(context, atom)

    with context.transaction(title="package", name=atom) as action:
        # Query current state
        installed = is_installed(context, atom)

        # Record this initial state, and return early
        # if there is nothing to do
        action.initial_state(installed=installed)
        should_install = (state == "present")
        if installed == should_install:
            return action.unchanged()

        # Record the final state
        action.final_state(installed=should_install)

        # Apply actions to reach new state, if we aren't in pretend mode
        if not context.pretend:
            if should_install:
                install(context, atom)
            else:
                uninstall(context, atom)

        # Return success
        return action.success()
