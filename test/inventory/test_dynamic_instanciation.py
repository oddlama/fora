import os
import fora.globals as G
import fora.loader

def test_dynamic_instanciation(request):
    os.chdir(request.fspath.dirname)
    hosts = ["host1", "host2", ("host3", "hosts/host_templ.py"), ("host4", "hosts/host_templ.py")]
    expected_files = ["host1.py", "host2.py", "host_templ.py", "host_templ.py"]

    fora.loader.load_site(hosts)
    assert G.inventory is not None

    for i in hosts:
        if isinstance(i, tuple):
            i = i[0]
        assert i in G.hosts

    for h, e in zip(G.hosts.values(), expected_files):
        assert hasattr(h, 'pyfile')
        assert getattr(h, 'pyfile', None) == e

    os.chdir(request.config.invocation_dir)
