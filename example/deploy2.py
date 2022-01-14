from fora.operations import files
from fora import script

@script.Params
class params:
    filename: str

#print(f"[+] Run script {__file__} on host {host.name}")
#local.script(name="Run script",
#             script="deploy.py")

print(params.filename)

with script.defaults():
    pass

files.upload_content(name=params.filename,
    content=b"a\n",
    dest="/tmp/save_1",
    mode="755")
