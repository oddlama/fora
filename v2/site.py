#!/usr/bin/env python3

# TODO templating context has:

@Group(name="servers")
class GroupServers:
    pass

@Host(name="chef", ssh_host="root@localhost")
class HostChef:
    pass

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
def site(reg):
    if registry.host("chef") in reg.group("desktops"):
        install_ssh()

simple_automation.run_if_main()
