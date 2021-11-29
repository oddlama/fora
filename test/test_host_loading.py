import fora.loader

def test_init():
    # This function is needed to init fora global state,
    # which we will test and need for testing.
    fora.loader.load_site([])

def test_load_host_url():
    h = fora.loader.load_host("ssh://user@some.localhost")
    assert h.url == "ssh://user@some.localhost"

def test_load_host_from_file():
    h = fora.loader.load_host("test", "test/inventory/hosts/host1.py")
    assert h.name == "test"
    assert hasattr(h, 'pyfile')
    assert getattr(h, 'pyfile') == "host1.py"
