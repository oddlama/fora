import pytest
from typing import Any, cast
from fora.connectors.ssh import SshConnector

import fora.loader
from fora.types import HostType

def create_host(name: str):
    ret = cast(HostType, fora.loader.DefaultHost())
    meta = HostType(name=name, _loaded_from="__test_internal__", url=name)
    meta.transfer(ret)
    return ret

def test_explicit_connector():
    class TestConnector:
        pass
    test_connector = TestConnector()

    h = cast(Any, create_host("ssh://red@herring.sea"))
    h.connector = test_connector

    fora.loader.resolve_connector(h)
    assert h.connector is test_connector

def test_connector_invalid():
    h = create_host("cannotresolve")
    with pytest.raises(SystemExit):
        fora.loader.resolve_connector(h)

def test_connector_ssh():
    h = cast(Any, create_host("ssh://user@host.localhost"))

    fora.loader.resolve_connector(h)
    assert h.connector is SshConnector

def test_connector_unknown():
    h = cast(Any, create_host("unknown://user@host.localhost"))

    with pytest.raises(SystemExit):
        fora.loader.resolve_connector(h)
