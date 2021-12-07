from fora.operations import files
from fora.script import defaults, script_params

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
