import os
import pytest

import fora.globals as G
import fora.loader

def test_init():
    class DefaultArgs:
        debug = False
        diff = False
    G.args = DefaultArgs()

def test_group_variable_conflict(request, capsys):
    os.chdir(request.fspath.dirname)

    with pytest.raises(SystemExit):
        fora.loader.load_site(["ssh://dummy@example.com"])
    _, err = capsys.readouterr()
    assert "conflict" in err

    os.chdir(request.config.invocation_dir)
