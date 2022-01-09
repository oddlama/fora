import os
from fora.utils import FatalError
import pytest
import fora.loader

def test_missing_hosts(request):
    os.chdir(request.fspath.dirname)
    with pytest.raises(FatalError, match=r"must define a list of hosts"):
        fora.loader.load_inventory_from_file_or_url("mock_inventories/missing_definition.py")

    os.chdir(request.config.invocation_dir)
