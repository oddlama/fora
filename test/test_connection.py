import hashlib
import os
import pytest
import subprocess
from typing import cast

import fora.globals as G
import fora.host
import fora.loader
import fora.script
from fora.connection import Connection
from fora.connectors.tunnel_dispatcher import RemoteOSError
from fora.types import HostType, ScriptType

hostname = "ssh://root@localhost"
host: HostType = cast(HostType, None)
connection: Connection = cast(Connection, None)

def test_init(pytestconfig):
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

def test_run_id():
    ret = connection.run(["id"])
    assert ret.returncode == 0
    assert ret.stdout is not None
    stdout = ret.stdout.decode('utf-8', 'ignore')
    assert "uid=0(root)" in stdout
    assert "gid=0(root)" in stdout
    assert ret.stderr == b""

def test_run_id_as_user_nobody():
    ret = connection.run(["id"], user="nobody")
    assert ret.returncode == 0
    assert ret.stdout is not None
    stdout = ret.stdout.decode('utf-8', 'ignore')
    parts = stdout.split(" ")
    assert "nobody" in parts[0]
    assert "root" in parts[1]
    assert ret.stderr == b""

def test_run_id_as_group_nobody():
    ret = connection.run(["id"], group="nobody")
    assert ret.returncode == 0
    assert ret.stdout is not None
    stdout = ret.stdout.decode('utf-8', 'ignore')
    parts = stdout.split(" ")
    assert "root" in parts[0]
    assert "nobody" in parts[1]
    assert ret.stderr == b""

def test_run_id_as_user_nobody_group_nobody():
    ret = connection.run(["id"], user="nobody", group="nobody")
    assert ret.returncode == 0
    assert ret.stdout is not None
    stdout = ret.stdout.decode('utf-8', 'ignore')
    parts = stdout.split(" ")
    assert "nobody" in parts[0]
    assert "nobody" in parts[1]
    assert ret.stderr == b""

def test_run_pwd():
    ret = connection.run(["pwd"])
    assert ret.returncode == 0
    assert ret.stdout == b"/tmp\n"
    assert ret.stderr == b""

def test_run_pwd_in_var_tmp():
    ret = connection.run(["pwd"], cwd="/var/tmp")
    assert ret.returncode == 0
    assert ret.stdout == b"/var/tmp\n"
    assert ret.stderr == b""

def test_resolve_user_self():
    assert connection.resolve_user(None) == "root"

def test_resolve_user_root_by_uid():
    assert connection.resolve_user("0") == "root"

def test_resolve_user_nobody():
    assert connection.resolve_user("nobody") == "nobody"

def test_resolve_group_self():
    assert connection.resolve_group(None) == "root"

def test_resolve_group_root_by_uid():
    assert connection.resolve_group("0") == "root"

def test_resolve_group_nobody():
    assert connection.resolve_group("nobody") == "nobody"

@pytest.mark.parametrize("n", [0, 1, 8, 32, 128, 1024, 1024 * 32, 1024 * 256])
def test_upload_download(n):
    content = os.urandom(n)
    connection.upload("/tmp/__pytest_fora_upload", content=content)
    assert connection.download("/tmp/__pytest_fora_upload") == content
    assert connection.download_or("/tmp/__pytest_fora_upload") == content
    stat = connection.stat("/tmp/__pytest_fora_upload", sha512sum=True)
    assert stat is not None
    assert stat.type == "file"
    assert stat.size == n
    assert stat.sha512sum == hashlib.sha512(content).digest()

def test_stat_nonexistent():
    stat = connection.stat("/tmp/__nonexistent")
    assert stat is None

def test_download_nonexistent():
    assert connection.download_or("/tmp/__nonexistent") == None
    with pytest.raises(ValueError):
        assert connection.download("/tmp/__nonexistent")

def test_close_connection():
    connection.__exit__(None, None, None)
    assert host.connection is None
