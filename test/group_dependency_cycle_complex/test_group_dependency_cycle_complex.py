import os
import pytest

import fora.globals as G
import fora.loader
from fora.utils import FatalError

def test_init():
    class DefaultArgs:
        debug = False
        diff = False
    G.args = DefaultArgs()

def test_group_dependency_cycle_complex(request):
    os.chdir(request.fspath.dirname)

    with pytest.raises(FatalError, match="cycle"):
        fora.loader.load_inventory("inventory.py")

    os.chdir(request.config.invocation_dir)
