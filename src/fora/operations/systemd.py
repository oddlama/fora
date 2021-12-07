"""Provides operations related to the systemd init system."""

from typing import Optional

from fora import globals as G
from fora.operations.api import Operation, OperationResult, operation
from fora.operations.utils import service_manager
import fora.host

@operation("systemctl")
def daemon_reload(user_mode: bool = False,
                  name: Optional[str] = None,
                  check: bool = True,
                  op: Operation = Operation.internal_use_only) -> OperationResult:
    """
    Manages a systemd unit.

    Parameters
    ----------
    user_mode
        Whether `systemctl --user` should be used to make user specific changes.
    name
        The name for the operation.
    check
        If True, returning `op.failure()` will raise an OperationError. All manually raised
        OperationErrors will be propagated. When False, any manually raised OperationError will
        be caught and `op.failure()` will be returned with the given message while continuing execution.
    op
        The operation wrapper. Must not be supplied by the user.
    """
    _ = (name, check) # Processed automatically.
    op.desc("daemon_reload")
    conn = fora.host.current_host.connection

    # This operation has no dynamic state.
    op.initial_state(reloaded=False)
    op.final_state(reloaded=True)

    if not G.args.dry:
        if user_mode:
            conn.run(["systemctl", "--user", "daemon_reload"])
        else:
            conn.run(["systemctl", "daemon_reload"])

    return op.success()

@service_manager(command="systemctl")
@operation("service")
def service(service: str, # pylint: disable=redefined-outer-name
            state: Optional[str] = None,
            enabled: Optional[bool] = None,
            user_mode: bool = False,
            name: Optional[str] = None,
            check: bool = True,
            op: Operation = Operation.internal_use_only) -> OperationResult:
    """
    Manages a systemd unit.

    Parameters
    ----------
    service
        The unit to manage.
    state
        The desired state of the unit. Valid options are `started`, `restarted`, `reloaded` and `stopped`.
        If None, the service's current state will not be changed.
    enabled
        Whether the unit should be started on boot.
    user_mode
        Whether `systemctl --user` should be used to make user specific changes.
    name
        The name for the operation.
    check
        If True, returning `op.failure()` will raise an OperationError. All manually raised
        OperationErrors will be propagated. When False, any manually raised OperationError will
        be caught and `op.failure()` will be returned with the given message while continuing execution.
    op
        The operation wrapper. Must not be supplied by the user.
    """
    _ = (name, check) # Processed automatically.
    op.desc(service)
    conn = fora.host.current_host.connection

    state_actions: dict[str, str] = {
        "started": "start",
        "restarted": "restart",
        "reloaded": "reload",
        "stopped": "stop",
    }

    if state is not None and state not in state_actions:
        raise ValueError(f"invalid target state '{state}'")

    # Examine current state
    systemd_active_state = conn.run(["systemctl", "show", "--value", "--property", "ActiveState", "--", service]).stdout
    if (systemd_active_state or b"").decode('utf-8', errors='ignore').strip() in ["active", "activating"]:
        cur_state = "started"
    else:
        cur_state = "stopped"

    systemd_unit_file_state = conn.run(["systemctl", "show", "--value", "--property", "UnitFileState", "--", service]).stdout
    cur_enabled = (systemd_unit_file_state or b"").decode('utf-8', errors='ignore').strip() == "enabled"

    op.initial_state(state=cur_state, enabled=cur_enabled)
    op.final_state(state=state, enabled=enabled)

    # Return success if nothing needs to be changed
    if op.unchanged(ignore_none=True):
        return op.success()

    # Apply actions to reach desired state, but only if we are not doing a dry run
    if not G.args.dry:
        base_command = ["systemctl", "--user"] if user_mode else ["systemctl"]
        if op.changed("state") and state is not None:
            conn.run(base_command + [state_actions[state], "--", service])

        if op.changed("enabled") and enabled is not None:
            conn.run(base_command + ["enable" if enabled else "disable", "--", service])

    return op.success()
