import pytest

from fora.main import main
import fora
import fora.loader

def test_init():
    # This function is needed to init fora global state,
    # which we will test and need for testing.
    fora.loader.load_inventory("local:")

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
