from fora.operations import files, local

files.template("c", "/tmp/c")
local.script(name="DDDDD", script="../sub2/deploy.py")
