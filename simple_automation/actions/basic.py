from simple_automation import Context, LogicError, RemoteExecError
from jinja2.exceptions import TemplateNotFound
from jinja2 import Template, Environment, FileSystemLoader

jinja2_env = Environment(
    loader=FileSystemLoader('templates', followlinks=True),
    autoescape=False)

def _template_str(context: Context, template_str):
    template = Template(template_str)
    return template.render(context.vars())

def mode_to_str(mode):
    return f"{mode:>03o}"

def resolve_mode_owner_group(context: Context, mode, owner, group):
    # Resolve mode to string
    resolved_mode = mode_to_str(context.dir_mode if mode is None else mode)

    # Resolve owner name/uid to name
    owner = context.owner if owner is None else owner
    remote_cmd_owner_id = context.remote_exec(["id", "-nu", owner])
    if remote_cmd_owner_id.return_code != 0:
        raise LogicError(f"Could not resolve remote user '{owner}'")
    resolved_owner = remote_cmd_owner_id.stdout.strip()

    # Resolve group name/gid to name
    group = context.group if group is None else group
    remote_cmd_group_id = context.remote_exec(["id", "-ng", group])
    if remote_cmd_group_id.return_code != 0:
        raise LogicError(f"Could not resolve remote group '{group}'")
    resolved_group = remote_cmd_group_id.stdout.strip()

    # Return resolved tuple
    return (resolved_mode, resolved_owner, resolved_group)

def directory(context: Context, path: str, mode=None, owner=None, group=None):
    """
    Creates the given directory on the remote. Will use the context default
    permissions if not explicitly given.
    """
    path = _template_str(context, path)
    with context.transaction(f"[dir] {path}") as action:
        mode, owner, group = resolve_mode_owner_group(context, mode, owner, group)

        # Get previous state
        stat = context.remote_exec(["stat", "-c", "%a %u %g", path])
        if stat.return_code == 0:
            # Parse and canonicalize output
            cur_mode, cur_owner, cur_group = stat.stdout.strip().split(" ")
            cur_mode, cur_owner, cur_group = resolve_mode_owner_group(context, int(cur_mode, 8), cur_owner, cur_group)

            # Record the initial state
            action.initial_state(exists=True, mode=cur_mode, owner=cur_owner, group=cur_group)
            if mode == cur_mode and owner == cur_owner and group == cur_group:
                return action.unchanged()
        else:
            # Record the initial state
            action.initial_state(exists=False, mode=None, owner=None, group=None)

        # Record the final state
        action.final_state(exists=True, mode=mode, owner=owner, group=group)
        # Apply actions to reach new state, if we aren't in pretend mode
        if not context.pretend:
            try:
                # If stat failed, the directory doesn't exist and we need to create it.
                if stat.return_code != 0:
                    context.remote_exec(["mkdir", path], checked=True)

                # Set permissions
                context.remote_exec(["chown", f"{owner}:{group}", path], checked=True)
                context.remote_exec(["chmod", mode, path], checked=True)
            except RemoteExecError as e:
                return action.failure(str(e))

        # Return success
        return action.success()

def directories(context: Context, paths: list, mode=None, owner=None, group=None):
    for path in paths:
        directory(context, path, mode, owner, group)

def template(context: Context, src: str, dst: str, mode=None, owner=None, group=None):
    src = _template_str(context, src)
    dst = _template_str(context, dst)

    try:
        template = jinja2_env.get_template(src)
    except TemplateNotFound as e:
        raise LogicError("template not found: " + str(e))

    content = template.render(context.vars())
    print(f"template {src} -> {dst}")
    print(content)
