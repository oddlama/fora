from simple_automation.script import this, host
from simple_automation.operations import local

local.script(name="Run script",
             script="deploy.py")

#print(f"[+] Run script {__file__} on host {host.meta.id}")
#
#if "desktops" in host.meta.groups:
#    print("is desktop")
#
#print("[+] Script done")
