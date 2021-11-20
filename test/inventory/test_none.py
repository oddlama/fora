import fora.globals as G
import fora.loader

def test_none():
    fora.loader.load_site([])
    assert G.inventory is not None
    assert G.inventory.hosts == []
