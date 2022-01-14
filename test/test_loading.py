import pytest

from fora.main import main
import fora
import fora.loader

def test_init():
    # This function is needed to init fora global state,
    # which we will test and need for testing.
    fora.loader.load_inventory("local:")

def test_load_host_url():
    h = fora.loader.load_host("some.localhost", "ssh://user@some.localhost")
    assert h.url == "ssh://user@some.localhost"

def test_load_host_from_file():
    h = fora.loader.load_host(name="test", url="ssh://test", module_file="test/inventory/mock_inventories/hosts/host1.py")
    assert h.name == "test"
    assert hasattr(h, 'pyfile')
    assert getattr(h, 'pyfile') == "host1.py"

def test_group_functions_from_outside_definition():
    assert fora.group is None

def test_host_functions_from_outside_definition():
    assert fora.host is None

def test_help_output():
    with pytest.raises(SystemExit) as e:
        main(["--help"])
    assert e.value.code == 0

def test_invalid_args():
    with pytest.raises(SystemExit) as e:
        main(["--whatisthis_nonexistent"])
    assert e.value.code == 1
