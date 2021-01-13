#!/usr/bin/env python3

from simple_automation import Manager, Task

def main():
    manager = Manager()
    #manager.defaults(dir_mode=0o700, file_mode=0o600, owner="root", group="root")

    #manager.add_group("base")

    #manager.add_host("lyra", "192.168.1.1")
    #  hosts.add("lyra", "192.168.1.1", lyra)
    #  hosts.add("cerev", "192.168.1.1", cerev)
    #  hosts.add("chef", "192.168.1.1", chef)

    manager.run()


if __name__ == "__main__":
    main()
