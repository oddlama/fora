import os
import pytest
from typing import cast

import fora.globals as G
import fora.host
import fora.loader
import fora.script
from fora.operations import local, files
from fora.connection import Connection
from fora.types import HostType, ScriptType

hostname = "ssh://root@localhost"
host: HostType = cast(HostType, None)
connection: Connection = cast(Connection, None)

def test_init():
    class DefaultArgs:
        debug = False
        diff = True
        dry = False
        changes = True
        debug = True
        verbose = 99
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

def test_local_script(capsys):
    local.script(script="test/operations/subdeploy.py")
    out, _ = capsys.readouterr()
    assert "subdeploy executed" in out

def test_files_directory():
    files.directory(path="/tmp/__pytest_fora")
    assert os.path.isdir("/tmp/__pytest_fora")

    files.directory(path="/tmp/__pytest_fora", present=False)
    assert not os.path.exists("/tmp/__pytest_fora")

    files.directory(path="/tmp/__pytest_fora", mode="755", present=True)
    assert os.path.isdir("/tmp/__pytest_fora")

def test_files_file():
    files.file(path="/tmp/__pytest_fora/testfile", mode="755")
    assert os.path.isfile("/tmp/__pytest_fora/testfile")

def test_files_link():
    files.link(path="/tmp/__pytest_fora/testlink", target="/tmp/__pytest_fora/testfile")
    assert os.path.islink("/tmp/__pytest_fora/testlink")

def test_files_upload_content():
    content = os.urandom(512)
    files.upload_content(dest="/tmp/__pytest_fora/testlink", content=content, mode="755")
    with open("/tmp/__pytest_fora/testlink", 'rb') as f:
        assert f.read() == content

def test_cleanup_directory():
    files.directory("/tmp/__pytest_fora", present=False)
    assert not os.path.exists("/tmp/__pytest_fora")

def test_close_connection():
    connection.__exit__(None, None, None)
    assert host.connection is None
