from simple_automation import this, host
from simple_automation.operations import local, files

print(f"[+] Run script {__file__} on host {host.name}")
local.script(name="Run script",
             script="deploy.py")

files.directory(name="Create a temporary directory",
                path="/tmp/abc_755",
                mode="755")
files.directory(name="Create a temporary directory",
                path="/tmp/abc_700",
                mode="700")
files.directory(name="Create a temporary directory",
                path="/tmp/abc_def")
