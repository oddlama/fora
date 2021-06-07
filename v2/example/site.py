#!/usr/bin/env python3

# TODO templating context has:

inv.host("chef", ssh_host="root@localhost", groups=[])

@Inventory
def define_inventory():
    inv.add_host("chef", ssh_host="root@localhost", groups=[])

@Task(description = "Sets up access to the tracking repository")
def setup_tracking(host):
    # Create tracking user
    user(host, name="tracking", home="{{ tracking.home }}")

    # Copy tracking ssh key
    with host.defaults(owner="tracking", group="tracking"):
        directory(host, path="{{ tracking.home }}/.ssh")
        template(host, content="{{ tracking.id_ed25519 }}", dst="{{ tracking.home }}/.ssh/id_ed25519")
        template(host, content="{{ tracking.id_ed25519_pub }}", dst="{{ tracking.home }}/.ssh/id_ed25519.pub")

@Task()
def install_ssh(host):
    pass

@Playbook
def site(reg, host, cvars):
    if host in reg.group("desktops"):
        reg.task(setup_tracking)



######## inventory.py ################################################

hosts = [ define_host("cerev", ssh_host="root@localhost", groups=["desktops"])
        ]

######## groups/all.py ################################################

some_dict = {'a': "xxx"}

######## groups/desktops.py ################################################

some_var = "juhuu"

######## tasks/mytask.py ################################################

some_default = "yolo"
# recommended naming scheme for task-contained variables:
mytask_var_1 = "test"
some_needed_var = require()
some_needed_var = require("error message if not set")

######## tasks/track_installed_packages.py ################################################

identifier = "track_installed_packages"
description = "Tracks all installed packages"
tracking_paths = ["{{ tracking.home }}/installed_packages"]

def run(self, context):
    save_output(context, command=["qlist", "-CIv"],
                dst="{{ tracking.home }}/installed_packages",
                desc="Query installed packages")

######## deploy.py ################################################

include("tasks/systemd.py")
include("tasks/track_installed_packages.py")
