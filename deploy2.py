from simple_automation import this, host
from simple_automation.operations import local, files

#print(f"[+] Run script {__file__} on host {host.name}")
#local.script(name="Run script",
#             script="deploy.py")

files.upload_content(name="saveeeeee",
             content=b"a\n",
             dest="/tmp/save_1",
             mode="755")
files.upload_content(name="saveeeeee",
             content=b"a\n",
             dest="/tmp/save_1",
             mode="700")
files.upload_content(name="saveeeeee",
             content=b"b\n",
             dest="/tmp/save_1",
             mode="700")
files.upload_content(name="saveeeeee",
             content=b"b\n",
             dest="/tmp/save_1",
             mode="700")
files.upload_dir(name="Create a temporary directory",
                 src="groups", dest="/tmp/mygroups")
files.template_content(name="templ content",
                       content="host.name = {{host.name}}\n",
                       dest="/tmp/tmpl")
files.directory(name="Create a temporary directory",
          path="/tmp/abc_755",
          mode="755")
files.directory(name="Create a temporary directory",
          path="/tmp/abc_700",
          mode="700")
files.directory(name="Create a temporary directory",
          path="/tmp/abc_def")
