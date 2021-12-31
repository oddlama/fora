import fora.globals as G
import fora.loader

def test_none():
    fora.loader.load_inventory_object(fora.loader.ImmediateInventory([]))
    assert G.inventory is not None
    assert G.inventory.hosts == []
