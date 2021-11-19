import fora.globals as G
import fora.loader

def test_default_inventory():
    fora.loader.load_site([])
    assert G.inventory.hosts == []
