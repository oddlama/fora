import os
import pytest
import fora.loader

def test_missing_hosts(request):
    os.chdir(request.fspath.dirname)
    with pytest.raises(SystemExit):
        fora.loader.load_site(["mock_inventories/missing_definition.py"])

    os.chdir(request.config.invocation_dir)
