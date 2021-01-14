#!/usr/bin/env python3

from simple_automation import Manager, Context
from tasks import TaskZsh


def main():
    manager = Manager()
    context = Context()
    # manager.defaults(dir_mode=0o700, file_mode=0o600, owner="root", group="root")

    # manager.add_group("base")
    # hosts.add("localhost", "localhost")
    TaskZsh().run(context)

    manager.run()


if __name__ == "__main__":
    main()
