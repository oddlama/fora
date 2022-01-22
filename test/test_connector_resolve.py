from dataclasses import dataclass
from types import SimpleNamespace
from fora.utils import FatalError
import pytest
from typing import Any, cast
from fora.connectors.ssh import SshConnector

from fora.types import HostWrapper

def create_host(name: str):
    wrapper = HostWrapper(name=name, url=name)
    wrapper.wrap(SimpleNamespace())
    return wrapper

def test_explicit_connector():
    @dataclass
    class TestConnector:
        name: str
        url: str

    h = cast(Any, create_host("ssh://red@herring.sea"))
    h.connector = TestConnector

    assert isinstance(h.create_connector(), TestConnector)

def test_connector_invalid():
    h = create_host("cannotresolve")
    with pytest.raises(FatalError, match=r"Url doesn't include a schema and no connector was specified"):
        h.create_connector()

def test_connector_ssh():
    h = cast(Any, create_host("ssh://user@host.localhost"))
    assert isinstance(h.create_connector(), SshConnector)

def test_connector_unknown():
    h = cast(Any, create_host("unknown://user@host.localhost"))

    with pytest.raises(FatalError, match=r"No connector found for schema"):
        h.create_connector()
