import os
import pytest

import fora.globals as G
import fora.loader

def test_init():
    class DefaultArgs:
        debug = False
        diff = False
    G.args = DefaultArgs()

def test_group_dependency_cycle_self(request):
    os.chdir(request.fspath.dirname)

    with pytest.raises(ValueError) as e:
        fora.loader.load_site(["ssh://dummy@example.com"])
        assert "dependency to self" in str(e.value)

    os.chdir(request.config.invocation_dir)
