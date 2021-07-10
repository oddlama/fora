from simple_automation import this, host
from simple_automation.operations import local

local.script(name="Run script",
             script="deploy.py")

print(f"[+] Run script {__file__} on host {host.name}")
#
#if "desktops" in host.groups:
#    print("is desktop")
#
#print("[+] Script done")
