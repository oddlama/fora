import os
import fora.loader
import fora.globals as G

def test_missing_hosts(request):
    os.chdir(request.fspath.dirname)

    fora.loader.load_site(["inventory.py"])
    for i in ["host1", "host2", "host3", "host4", "host5"]:
        assert i in G.hosts

    assert G.hosts["host1"].groups == set(["all", "desktops"])
    assert G.hosts["host2"].groups == set(["all", "desktops", "somehosts"])
    assert G.hosts["host3"].groups == set(["all", "desktops", "only34"])
    assert G.hosts["host4"].groups == set(["all", "somehosts", "only34"])
    assert G.hosts["host5"].groups == set(["all"])

    assert G.hosts["host1"].overwrite_host == "host1"
    assert G.hosts["host2"].overwrite_host == "host2"
    assert G.hosts["host3"].overwrite_host == "host3"
    assert G.hosts["host4"].overwrite_host == "host4"
    assert G.hosts["host5"].overwrite_host == "host5"

    assert G.hosts["host1"].overwrite_group == "desktops"
    assert G.hosts["host2"].overwrite_group == "somehosts"
    assert G.hosts["host3"].overwrite_group == "desktops"
    assert G.hosts["host4"].overwrite_group == "somehosts"
    assert G.hosts["host5"].overwrite_group == "all"

    os.chdir(request.config.invocation_dir)
