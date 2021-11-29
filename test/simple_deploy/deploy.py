from fora.host import current_host as host
from fora.operations import files

some_script_default = "def"

files.template_content(
    dest="/tmp/__pytest_fora/test_deploy",
    content="{{ myvar }}",
    context=dict(myvar="testdeploy made this"),
    mode="644")

assert not hasattr(host, 'bullshit')
assert hasattr(host, 'some_script_default')
assert getattr(host, 'some_script_default') == "def"
