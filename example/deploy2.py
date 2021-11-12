from simple_automation.operations import files
from simple_automation.script import defaults, script_params

@script_params
class params:
    filename: str

#print(f"[+] Run script {__file__} on host {host.name}")
#local.script(name="Run script",
#             script="deploy.py")

with defaults():
    pass

files.upload_content(name=params.filename,
    content=b"a\n",
    dest="/tmp/save_1",
    mode="755")
files.upload_content(name=params.filename,
    content=b"a\n",
    dest="/tmp/save_1",
    mode="700")
files.upload_content(name=params.filename,
    content=b"b\n",
    dest="/tmp/save_1",
    mode="700")
files.upload_content(name=params.filename,
    content=b"b\n",
    dest="/tmp/save_1",
    mode="700")
files.upload_dir(name="Create a temporary directory",
    src="groups", dest="/tmp/mygroups")
files.template(name="temaefaef",
    src="test.j2",
    dest="/tmp/tmpl2")
files.template_content(name="templ content",
    content="{{simple_automation_managed}}\nhost.name = {{host.name}}\n{{onlyhost}}\n{{onlydesktops}}\n",
    dest="/tmp/tmpl")
files.directory(name="Create a temporary directory",
    path="/tmp/abc_755",
    mode="755")
files.directory(name="Create a temporary directory",
    path="/tmp/abc_700",
    mode="700")
files.directory(name="Create a temporary directory",
    path="/tmp/abc_def")
