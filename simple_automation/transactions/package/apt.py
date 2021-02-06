from simple_automation import Context
from simple_automation.transactions.basic import _template_str

def is_installed(context: Context, atom: str, packages=None):
    remote_query = context.remote_exec(["dpgk-query", "--show", "--showformat=${Status}", atom], checked=True)
    return "ok installed" in remote_query.stdout

def package(context: Context, atom: str, state="present", oneshot=False, opts=[]):
    """
    Installs or uninstalls (depending if state == "present" or "absent") the given
    package atom. Additional options to apt-get can be passed via opts, and will be appended
    before the package atom. opts will be templated.
    """
    if state not in ["present", "absent"]:
        raise LogicError(f"Invalid package state '{state}'")

    atom = _template_str(context, atom)
    opts = [_template_str(context, o) for o in opts]

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
                apt_cmd = ["apt-get", "install"]
                apt_cmd.extend(opts)
                apt_cmd.append(atom)

                context.remote_exec(apt_cmd, checked=True)
            else:
                context.remote_exec(["apt-get", "remove"] + opts + [atom], checked=True)

        # Return success
        return action.success()
