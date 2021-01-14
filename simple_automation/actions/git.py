from simple_automation import Context
from simple_automation.checks import check_valid_dir


def clone(
    context: Context, url: str, dst: str, update: bool = False, depth=None, **kwargs
) -> None:
    check_valid_dir(dst)

    print(f"clone {url} -> {dst}, update={update}, depth={depth}")
    #if not dst exists:
    #    state = run_process(["git", "clone", url, ])
    #    clone()
    #    return State(changed=True, updated=False)

    #if update:
    #    state = run_process(["git", "pull"], cwd=dst)
    #    update()
    #    return State(changed=True, updated=True)

    #return State(changed=False, updated=False)
