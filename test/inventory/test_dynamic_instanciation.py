import os
import fora
import fora.globals as G
import fora.loader

def test_dynamic_instanciation(request):
    os.chdir(request.fspath.dirname)

    try:
        fora.loader.load_inventory("mock_inventories/simple_test.py")
        assert fora.inventory is not None

        hosts = fora.inventory.hosts
        expected_files = ["host1.py", "host2.py", "host_templ.py", "host_templ.py"]

        for i in hosts:
            if isinstance(i, tuple):
                i = i[0]
            assert i in G.hosts

        for h, e in zip(G.hosts.values(), expected_files):
            assert hasattr(h, 'pyfile')
            assert getattr(h, 'pyfile', None) == e
    finally:
        os.chdir(request.config.invocation_dir)

def test_inventory_global_variables(request):
    os.chdir(request.fspath.dirname)

    try:
        fora.loader.load_inventory("mock_inventories/single_host1.py")
        assert fora.inventory is not None

        assert "host1" in G.hosts
        assert G.hosts["host1"].inventory_var == "from_inventory"
    finally:
        os.chdir(request.config.invocation_dir)
