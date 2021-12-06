import grp
import hashlib
import os
import pwd
import pytest
import subprocess
from typing import cast

import fora.globals as G
import fora.host
import fora.loader
import fora.script
from fora.connection import Connection
from fora.connectors import tunnel_dispatcher as td
from fora.connectors.connector import connector
from fora.connectors.tunnel_connector import TunnelConnector
from fora.connectors.tunnel_dispatcher import RemoteOSError
from fora.types import HostType, ScriptType

hostname = "coverage:"
host: HostType = cast(HostType, None)
connection: Connection = cast(Connection, None)

@connector(schema='coverage')
class CoverageConnector(TunnelConnector):
    """A tunnel connector that provides fake remote access (always localhost) via a tunnel dispatcher subprocess."""

    def command(self) -> list[str]:
        command = ["python3", os.path.realpath(td.__file__)]
        if G.args.debug:
            command.append("--debug")
        return command

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

def current_test_user():
    return pwd.getpwuid(os.getuid()).pw_name

def current_test_group():
    return grp.getgrgid(os.getgid()).gr_name

def test_open_connection():
    global connection
    connection = Connection(host)
    connection.__enter__()
    assert host.connection is connection

    ctx = fora.script.defaults()
    defs = ctx.__enter__()
    current_user = current_test_user()
    current_group = current_test_group()
    assert defs.as_user == current_user
    assert defs.as_group == current_group
    assert defs.owner == current_user
    assert defs.group == current_group
    assert defs.cwd == "/tmp"
    assert int(defs.dir_mode, 8) == 0o700
    assert int(defs.file_mode, 8) == 0o600
    assert int(defs.umask, 8) == 0o77

def test_resolve_identity():
    current_user = current_test_user()
    current_group = current_test_group()
    assert connection.base_settings.as_user == current_user
    assert connection.base_settings.as_group == current_group
    assert connection.base_settings.owner == current_user
    assert connection.base_settings.group == current_group

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
    assert f"uid={os.getuid()}({current_test_user()})" in stdout
    assert f"gid={os.getgid()}({current_test_group()})" in stdout
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
    assert connection.resolve_user(None) == current_test_user()

def test_resolve_user_root_by_uid():
    assert connection.resolve_user("0") == "root"

def test_resolve_user_nobody():
    assert connection.resolve_user("nobody") == "nobody"

def test_resolve_user_invalid():
    with pytest.raises(ValueError):
        connection.resolve_user("_invalid_")

def test_resolve_group_self():
    assert connection.resolve_group(None) == current_test_group()

def test_resolve_group_root_by_uid():
    assert connection.resolve_group("0") == "root"

def test_resolve_group_nobody():
    assert connection.resolve_group("nobody") == "nobody"

def test_resolve_group_invalid():
    with pytest.raises(ValueError):
        connection.resolve_group("_invalid_")

@pytest.mark.parametrize("n", [0, 1, 8, 32, 128, 1024, 1024 * 32, 1024 * 256])
def test_upload_download(n):
    content = os.urandom(n)
    if os.path.exists("/tmp/__pytest_fora_upload"):
        os.remove("/tmp/__pytest_fora_upload")
    connection.upload("/tmp/__pytest_fora_upload", content=content)
    assert connection.download("/tmp/__pytest_fora_upload") == content
    assert connection.download_or("/tmp/__pytest_fora_upload") == content
    stat = connection.stat("/tmp/__pytest_fora_upload", sha512sum=True)
    assert stat is not None
    assert stat.type == "file"
    assert stat.size == n
    assert stat.sha512sum == hashlib.sha512(content).digest()
    os.remove("/tmp/__pytest_fora_upload")

def test_upload_owner_group():
    content = b"1234"
    if os.path.exists("/tmp/__pytest_fora_upload"):
        os.remove("/tmp/__pytest_fora_upload")
    connection.upload("/tmp/__pytest_fora_upload", content=content, mode="644", owner=str(os.getuid()), group=str(os.getgid()))
    assert connection.download("/tmp/__pytest_fora_upload") == content
    assert connection.download_or("/tmp/__pytest_fora_upload") == content
    stat = connection.stat("/tmp/__pytest_fora_upload", sha512sum=True)
    assert stat is not None
    assert stat.type == "file"
    assert stat.sha512sum == hashlib.sha512(content).digest()
    os.remove("/tmp/__pytest_fora_upload")

def test_stat_nonexistent():
    stat = connection.stat("/tmp/__nonexistent")
    assert stat is None

def test_download_nonexistent():
    assert connection.download_or("/tmp/__nonexistent") == None
    with pytest.raises(ValueError):
        assert connection.download("/tmp/__nonexistent")

def test_run_none_in_fields():
    ret = connection.connector.run(["true"], umask=None, user=None, group=None, cwd=None)
    assert ret.returncode == 0

def test_run_invalid_command():
    with pytest.raises(RemoteOSError, match=r"No such file or directory"):
        connection.run(["_invalid_"])

def test_run_invalid_umask():
    with pytest.raises(ValueError, match=r"invalid value.*given for field 'umask'"):
        connection.run(["true"], umask="_invalid_")

def test_run_invalid_user():
    with pytest.raises(ValueError, match=r"invalid value.*given for field 'user'"):
        connection.run(["true"], user="_invalid_")

def test_run_invalid_user_id():
    with pytest.raises(ValueError, match=r"invalid value.*given for field 'user'"):
        connection.run(["true"], user="1234567890")

def test_run_invalid_group():
    with pytest.raises(ValueError, match=r"invalid value.*given for field 'group'"):
        connection.run(["true"], group="_invalid_")

def test_run_invalid_group_id():
    with pytest.raises(ValueError, match=r"invalid value.*given for field 'group'"):
        connection.run(["true"], group="1234567890")

def test_run_invalid_cwd():
    with pytest.raises(ValueError, match=r"invalid value.*given for field 'cwd'"):
        connection.run(["true"], cwd="/_invalid_")

def test_upload_invalid_mode():
    with pytest.raises(ValueError, match=r"invalid value.*given for field 'mode'"):
        connection.upload("/invalid", content=b"", mode="_invalid_")

def test_upload_invalid_owner():
    with pytest.raises(ValueError, match=r"invalid value.*given for field 'owner'"):
        connection.upload("/invalid", content=b"", owner="_invalid_")

def test_upload_invalid_group():
    with pytest.raises(ValueError, match=r"invalid value.*given for field 'group'"):
        connection.upload("/invalid", content=b"", group="_invalid_")

def test_query_group_nonexistent():
    entry = connection.query_group("__nonexistent")
    assert entry is None

def test_query_user_nonexistent():
    entry = connection.query_user("__nonexistent")
    assert entry is None

def test_query_group():
    entry = connection.query_group("nobody")
    assert entry is not None
    assert entry.name == "nobody"

def test_query_user():
    with pytest.raises(RemoteOSError, match=r"Permission denied"):
        connection.query_user("nobody")

def test_close_connection():
    connection.__exit__(None, None, None)
    assert host.connection is None
