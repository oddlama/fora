#!/usr/bin/env python3

from simple_automation import Vault, Manager
from tasks import TaskZsh, TaskTrackPortage

# TODO - somehow offload definitions into vault
# TODO - track installed packages qlist -I in git
# TODO - error on using unbound variables in templates

# -------- Load encrypted variables from vault --------
vault = None #Vault("myvault.gpg", type='gpg')

# -------- Create Manager --------
manager = Manager()
manager.set("zsh.install", False)
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

# -------- Define Tasks --------
task_zsh = manager.add_task(TaskZsh)
task_track_portage = manager.add_task(TaskTrackPortage)

def run(context):
    """
    This function will be executed for each host context,
    and is your main customization point.
    """
    task_zsh.exec(context)
    task_track_portage.exec(context)

if __name__ == "__main__":
    manager.main(run)
