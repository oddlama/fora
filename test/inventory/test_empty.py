import os
import fora
import fora.loader

def test_empty(request):
    os.chdir(request.fspath.dirname)
    fora.loader.load_inventory("mock_inventories/empty.py")
    assert fora.inventory is not None
    assert fora.inventory.hosts == []

    os.chdir(request.config.invocation_dir)
