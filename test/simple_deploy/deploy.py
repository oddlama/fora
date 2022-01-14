from fora import host
from fora.operations import files

@Params
class params:
    filename: str = "def"

some_script_default = "def"

files.template_content(
    dest="/tmp/__pytest_fora/test_deploy",
    content="{{ myvar }}",
    context=dict(myvar="testdeploy made this"),
    mode="644")

assert params.filename == "def"
assert not hasattr(host, 'bullshit')
assert hasattr(host, 'some_script_default')
assert getattr(host, 'some_script_default') == "def"
