from fora.operations import local

local.script(script="deploy.py", recursive=True)
local.script(script="deploy_bad_recursive.py")
