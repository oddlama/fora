from simple_automation import Context


def create_dir(context: Context, path: str) -> None:
    print(f"create_dir {path}")

def create_dirs(context: Context, path: list) -> None:
    print(f"create_dirs {path}")

def template(context: Context, src: str, dst: str) -> None:
    print(f"template {src} -> {dst}")
