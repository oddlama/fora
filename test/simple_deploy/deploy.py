from fora.operations import files

files.template_content(
    dest="/tmp/__pytest_fora/test_deploy",
    content="{{ myvar }}",
    context=dict(myvar="testdeploy made this"),
    mode="644")
