import os
from typing import Any, cast
import fora.loader
import fora.globals as G

def test_simple_inventory(request):
    os.chdir(request.fspath.dirname)

    fora.loader.load_site(["inventory.py"])
    for i in ["host1", "host2", "host3", "host4", "host5"]:
        assert i in G.hosts

    assert G.hosts["host1"].groups == set(["all", "desktops"])
    assert G.hosts["host2"].groups == set(["all", "desktops", "somehosts"])
    assert G.hosts["host3"].groups == set(["all", "desktops", "only34"])
    assert G.hosts["host4"].groups == set(["all", "somehosts", "only34"])
    assert G.hosts["host5"].groups == set(["all"])

    assert not hasattr(G.hosts["host1"], '_bullshit')
    assert not hasattr(G.hosts["host2"], '_bullshit')
    assert not hasattr(G.hosts["host3"], '_bullshit')
    assert not hasattr(G.hosts["host4"], '_bullshit')
    assert not hasattr(G.hosts["host5"], '_bullshit')

    assert not hasattr(G.hosts["host1"], 'bullshit')
    assert not hasattr(G.hosts["host2"], 'bullshit')
    assert not hasattr(G.hosts["host3"], 'bullshit')
    assert not hasattr(G.hosts["host4"], 'bullshit')
    assert not hasattr(G.hosts["host5"], 'bullshit')

    assert getattr(G.hosts["host1"], '_loaded_from') is not None
    assert getattr(G.hosts["host2"], '_loaded_from') is not None
    assert getattr(G.hosts["host3"], '_loaded_from') is not None
    assert getattr(G.hosts["host4"], '_loaded_from') is not None
    assert getattr(G.hosts["host5"], '_loaded_from') is not None

    assert hasattr(G.hosts["host1"], 'value_from_all')
    assert hasattr(G.hosts["host2"], 'value_from_all')
    assert hasattr(G.hosts["host3"], 'value_from_all')
    assert hasattr(G.hosts["host4"], 'value_from_all')
    assert hasattr(G.hosts["host5"], 'value_from_all')

    assert hasattr(G.hosts["host1"], 'overwrite_host')
    assert hasattr(G.hosts["host2"], 'overwrite_host')
    assert hasattr(G.hosts["host3"], 'overwrite_host')
    assert hasattr(G.hosts["host4"], 'overwrite_host')
    assert hasattr(G.hosts["host5"], 'overwrite_host')

    assert cast(Any, G.hosts["host1"]).overwrite_host == "host1"
    assert cast(Any, G.hosts["host2"]).overwrite_host == "host2"
    assert cast(Any, G.hosts["host3"]).overwrite_host == "host3"
    assert cast(Any, G.hosts["host4"]).overwrite_host == "host4"
    assert cast(Any, G.hosts["host5"]).overwrite_host == "host5"

    assert hasattr(G.hosts["host1"], 'overwrite_group')
    assert hasattr(G.hosts["host2"], 'overwrite_group')
    assert hasattr(G.hosts["host3"], 'overwrite_group')
    assert hasattr(G.hosts["host4"], 'overwrite_group')
    assert hasattr(G.hosts["host5"], 'overwrite_group')

    assert cast(Any, G.hosts["host1"]).overwrite_group == "desktops"
    assert cast(Any, G.hosts["host2"]).overwrite_group == "somehosts"
    assert cast(Any, G.hosts["host3"]).overwrite_group == "desktops"
    assert cast(Any, G.hosts["host4"]).overwrite_group == "somehosts"
    assert cast(Any, G.hosts["host5"]).overwrite_group == "all"

    os.chdir(request.config.invocation_dir)
