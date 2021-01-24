from simple_automation import Context


def package(context: Context, name: str, state=None):
    print(f"portage.package {name}, {state}")
