from simple_automation import this, host
from simple_automation.operations import local

print(f"[+] Run script {__file__} on host {host.name}")

with this.defaults(as_user="malte"):
    with this.defaults(as_user="root"):
        with this.defaults(umask="755"):
            local.script(name="Run script",
                         script="deploy2.py")

if "desktops" in host.groups:
    print("is desktop")
