from fora.host import current_host as host
from fora.operations import local, system, git

somedefault = 134

#print(f"[+] Run script {__file__} on host {host.name}")
#files.directory(name="Create a temporary directory",
#                path="/tmp/abc_700",
#                mode="700")

local.script(name="Run script",
             script="deploy2.py",
             params=dict(filename="tolll"))

system.package("neovim")
system.service("chronyd", enabled=False)
system.service("chronyd", enabled=True)

# git.repo(name="Clone some wierd repo",
#          url="https://github.com/oddlama/fora",
#          path="/tmp/__fora__tmp__clone",
#          branch_or_tag="develop",
#          update_submodules=True,
#          shallow_submodules=True,
#          depth=1)

if "desktops" in host.groups:
    print("is desktop")
