import os
import fora.globals as G
import fora.loader

def test_empty(request):
    os.chdir(request.fspath.dirname)
    fora.loader.load_inventory_from_file_or_url("mock_inventories/empty.py")
    assert G.inventory is not None
    assert G.inventory.hosts == []

    os.chdir(request.config.invocation_dir)
