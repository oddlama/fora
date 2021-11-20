import os
import pytest
import fora.loader

def test_missing_hosts(request, capsys):
    os.chdir(request.fspath.dirname)
    with pytest.raises(SystemExit):
        fora.loader.load_site(["mock_inventories/missing_definition.py"])
    _, err = capsys.readouterr()
    assert "must define a list of hosts" in err

    os.chdir(request.config.invocation_dir)
