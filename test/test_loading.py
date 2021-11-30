import pytest

from fora.main import main
import fora.globals as G
import fora.group
import fora.host
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

def test_group_functions_from_outside_definition():
    with pytest.raises(RuntimeError, match="may only be called inside a group module definition"):
        fora.group.name()
    with pytest.raises(RuntimeError, match="may only be called inside a group module definition"):
        fora.group.before("")
    with pytest.raises(RuntimeError, match="may only be called inside a group module definition"):
        fora.group.before_all([""])
    with pytest.raises(RuntimeError, match="may only be called inside a group module definition"):
        fora.group.after("")
    with pytest.raises(RuntimeError, match="may only be called inside a group module definition"):
        fora.group.after_all([""])

def test_host_functions_from_outside_definition():
    with pytest.raises(RuntimeError, match="may only be called inside a host module definition"):
        fora.host.name()
    with pytest.raises(RuntimeError, match="may only be called inside a host module definition"):
        fora.host.add_group("")
    with pytest.raises(RuntimeError, match="may only be called inside a host module definition"):
        fora.host.add_groups([""])

def test_help_output():
    with pytest.raises(SystemExit) as e:
        main(["--help"])
    assert e.value.code == 0

def test_invalid_args():
    with pytest.raises(SystemExit) as e:
        main(["--whatisthis_nonexistent"])
    assert e.value.code == 1
