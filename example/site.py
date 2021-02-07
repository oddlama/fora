#!/usr/bin/env python3

from simple_automation import Vault, Manager
from tasks import TaskZsh, TaskTrackPortage, TaskTrackInstalledPackages

# TODO - somehow offload definitions into vault
# TODO - track installed packages qlist -I in git
# TODO - error on using unbound variables in templates

# -------- Load encrypted vault --------
vault = None#Vault("myvault.gpg", type='gpg')

# -------- Create Manager --------
manager = Manager()

# -------- Define Tasks --------
manager.add_task(TaskZsh)
manager.add_task(TaskTrackPortage)
manager.add_task(TaskTrackInstalledPackages)

# -------- Set global variables --------
manager.set("tasks.zsh.enabled", False)
manager.set("vault", vault)

# -------- Define Groups --------
desktop = manager.add_group("desktop")
desktop.set("global.is_desktop", True)

# -------- Define Hosts --------
my_laptop = manager.add_host("my_laptop", ssh_host="root@localhost")
my_laptop.set_ssh_port(2222)
my_laptop.add_group(desktop)
# You may set custom variables, which you can access later
# in any templated string.
my_laptop.hostname = "chef"

# TODO my_laptop.set("root_pw", vault_key="")

def run(context):
    """
    This function will be executed for each host context,
    and is your main customization point.
    """
    context.run_task(TaskZsh)
    context.run_task(TaskTrackPortage)
    context.run_task(TaskTrackInstalledPackages)

if __name__ == "__main__":
    manager.main(run)
