import subprocess
from typing import cast

import pytest
from fora.connection import Connection
from fora.connectors.tunnel_dispatcher import RemoteOSError
import fora.loader
import fora.host
import fora.script
import fora.globals as G
from fora.types import HostType, ScriptType

hostname = "ssh://root@localhost"
host: HostType = cast(HostType, None)
connection: Connection = cast(Connection, None)

def test_init():
    class DefaultArgs:
        debug = False
        diff = False
    G.args = DefaultArgs()
    fora.loader.load_site([hostname])

    global host
    host = G.hosts[hostname]
    fora.host.current_host = host
    fora.script._this = ScriptType("__internal_test", "__internal_test")

def test_open_connection():
    global connection
    connection = Connection(host)
    connection.__enter__()
    assert host.connection is connection

    ctx = fora.script.defaults()
    defs = ctx.__enter__()
    assert defs.as_user == "root"
    assert defs.as_group == "root"
    assert defs.owner == "root"
    assert defs.group == "root"
    assert defs.cwd == "/tmp"
    assert int(defs.dir_mode, 8) == 0o700
    assert int(defs.file_mode, 8) == 0o600
    assert int(defs.umask, 8) == 0o77

def test_resolve_identity():
    assert connection.base_settings.as_user == "root"
    assert connection.base_settings.as_group == "root"
    assert connection.base_settings.owner == "root"
    assert connection.base_settings.group == "root"

def test_run_false():
    with pytest.raises(subprocess.CalledProcessError) as e:
        connection.run(["false"])
    assert 1 == e.value.returncode

def test_run_false_unchecked():
    ret = connection.run(["false"], check=False)
    assert ret.returncode == 1
    assert ret.stdout == b""
    assert ret.stderr == b""

def test_run_true():
    ret = connection.run(["true"])
    assert ret.returncode == 0
    assert ret.stdout == b""
    assert ret.stderr == b""

def test_run_not_a_shell():
    with pytest.raises(RemoteOSError) as e:
        connection.run(["echo test"])
    assert e.value.errno == 2

def test_run_echo():
    ret = connection.run(["echo", "abc"])
    assert ret.returncode == 0
    assert ret.stdout == b"abc\n"
    assert ret.stderr == b""

def test_run_cat_input():
    ret = connection.run(["cat"], input=b"test\nb")
    assert ret.returncode == 0
    assert ret.stdout == b"test\nb"
    assert ret.stderr == b""

def test_close_connection():
    connection.__exit__(None, None, None)
    assert host.connection is None
