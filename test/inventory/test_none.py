import fora
import fora.loader

def test_none():
    fora.loader.load_inventory_object(fora.loader.ImmediateInventory([]))
    assert fora.inventory is not None
    assert fora.inventory.hosts == []
