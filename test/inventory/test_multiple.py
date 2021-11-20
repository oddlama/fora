import os
import fora.globals as G
import fora.loader

def test_multiple(request):
    os.chdir(request.fspath.dirname)
    fora.loader.load_site(["mock_inventories/single_host1.py", "host2"])
    assert G.inventory is not None
    assert len(G.hosts) == 2
    assert "host1" in G.hosts
    assert "host2" in G.hosts

    os.chdir(request.config.invocation_dir)
