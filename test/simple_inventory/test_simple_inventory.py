import os
from typing import Any, cast
import fora
import fora.loader

def test_simple_inventory(request):
    os.chdir(request.fspath.dirname)

    fora.loader.load_inventory("inventory.py")
    for i in ["host1", "host2", "host3", "host4", "host5"]:
        assert i in fora.inventory.loaded_hosts

    assert set(fora.inventory.loaded_hosts["host1"].groups) == set(["all", "desktops"])
    assert set(fora.inventory.loaded_hosts["host2"].groups) == set(["all", "desktops", "somehosts"])
    assert set(fora.inventory.loaded_hosts["host3"].groups) == set(["all", "desktops", "only34"])
    assert set(fora.inventory.loaded_hosts["host4"].groups) == set(["all", "somehosts", "only34"])
    assert set(fora.inventory.loaded_hosts["host5"].groups) == set(["all"])

    assert not hasattr(fora.inventory.loaded_hosts["host1"], '_bullshit')
    assert not hasattr(fora.inventory.loaded_hosts["host2"], '_bullshit')
    assert not hasattr(fora.inventory.loaded_hosts["host3"], '_bullshit')
    assert not hasattr(fora.inventory.loaded_hosts["host4"], '_bullshit')
    assert not hasattr(fora.inventory.loaded_hosts["host5"], '_bullshit')

    assert not hasattr(fora.inventory.loaded_hosts["host1"], 'bullshit')
    assert not hasattr(fora.inventory.loaded_hosts["host2"], 'bullshit')
    assert not hasattr(fora.inventory.loaded_hosts["host3"], 'bullshit')
    assert not hasattr(fora.inventory.loaded_hosts["host4"], 'bullshit')
    assert not hasattr(fora.inventory.loaded_hosts["host5"], 'bullshit')

    assert hasattr(fora.inventory.loaded_hosts["host1"], 'value_from_all')
    assert hasattr(fora.inventory.loaded_hosts["host2"], 'value_from_all')
    assert hasattr(fora.inventory.loaded_hosts["host3"], 'value_from_all')
    assert hasattr(fora.inventory.loaded_hosts["host4"], 'value_from_all')
    assert hasattr(fora.inventory.loaded_hosts["host5"], 'value_from_all')

    assert hasattr(fora.inventory.loaded_hosts["host1"], 'overwrite_host')
    assert hasattr(fora.inventory.loaded_hosts["host2"], 'overwrite_host')
    assert hasattr(fora.inventory.loaded_hosts["host3"], 'overwrite_host')
    assert hasattr(fora.inventory.loaded_hosts["host4"], 'overwrite_host')
    assert hasattr(fora.inventory.loaded_hosts["host5"], 'overwrite_host')

    assert cast(Any, fora.inventory.loaded_hosts["host1"]).overwrite_host == "host1"
    assert cast(Any, fora.inventory.loaded_hosts["host2"]).overwrite_host == "host2"
    assert cast(Any, fora.inventory.loaded_hosts["host3"]).overwrite_host == "host3"
    assert cast(Any, fora.inventory.loaded_hosts["host4"]).overwrite_host == "host4"
    assert cast(Any, fora.inventory.loaded_hosts["host5"]).overwrite_host == "host5"

    assert hasattr(fora.inventory.loaded_hosts["host1"], 'overwrite_group')
    assert hasattr(fora.inventory.loaded_hosts["host2"], 'overwrite_group')
    assert hasattr(fora.inventory.loaded_hosts["host3"], 'overwrite_group')
    assert hasattr(fora.inventory.loaded_hosts["host4"], 'overwrite_group')
    assert hasattr(fora.inventory.loaded_hosts["host5"], 'overwrite_group')

    assert cast(Any, fora.inventory.loaded_hosts["host1"]).overwrite_group == "desktops"
    assert cast(Any, fora.inventory.loaded_hosts["host2"]).overwrite_group == "somehosts"
    assert cast(Any, fora.inventory.loaded_hosts["host3"]).overwrite_group == "desktops"
    assert cast(Any, fora.inventory.loaded_hosts["host4"]).overwrite_group == "somehosts"
    assert cast(Any, fora.inventory.loaded_hosts["host5"]).overwrite_group == "all"

    os.chdir(request.config.invocation_dir)
