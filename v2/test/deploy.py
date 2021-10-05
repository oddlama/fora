from simple_automation import this, host
from simple_automation.operations import local

print(f"[+] Run script {__file__} on host {host.name}")
#local.script(name="Run script",
#             script="deploy.py")

with this.defaults(as_user="malte"):
    with this.defaults(as_user="root"):
        with this.defaults(umask="755"):
            pass

if "desktops" in host.groups:
    print("is desktop")
