import os
import pytest
from typing import cast

import fora.globals as G
import fora.host
import fora.loader
import fora.script
from fora.main import main
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
    files.file(path="/tmp/__pytest_fora/testfile", mode="644")
    assert os.path.isfile("/tmp/__pytest_fora/testfile")

def test_files_link():
    files.link(path="/tmp/__pytest_fora/testlink", target="/tmp/__pytest_fora/testfile")
    assert os.path.islink("/tmp/__pytest_fora/testlink")

def test_files_upload_content():
    content = os.urandom(512)
    files.upload_content(dest="/tmp/__pytest_fora/testcontent", content=content, mode="644")
    with open("/tmp/__pytest_fora/testcontent", 'rb') as f:
        assert f.read() == content

def test_files_upload():
    files.upload(src=__file__, dest="/tmp/__pytest_fora/testupload", mode="644")
    with open("/tmp/__pytest_fora/testupload", 'rb') as f:
        with open(__file__, 'rb') as g:
            assert f.read() == g.read()

def test_files_template_content():
    files.template_content(dest="/tmp/__pytest_fora/testtemplcontent", content="{{ myvar }}", context=dict(myvar="q948fhqh489f"), mode="644")
    with open("/tmp/__pytest_fora/testtemplcontent", 'rb') as f:
        assert f.read() == b"q948fhqh489f"

def test_files_template():
    files.template(src="test/templates/test.j2", dest="/tmp/__pytest_fora/testtempl", context=dict(myvar="graio208hfae"), mode="644")
    with open("/tmp/__pytest_fora/testtempl", 'rb') as f:
        assert f.read() == b"graio208hfae"

def files_upload_dir(dest):
    src = "test/simple_inventory"
    files.upload_dir(src=src, dest=dest, dir_mode="755", file_mode="644")

    if dest[-1] == "/":
        dest = os.path.join(dest, os.path.basename(src))
    for root, _, subfiles in os.walk(src):
        root = os.path.relpath(root, start=src)
        sroot = os.path.normpath(os.path.join(src, root))
        droot = os.path.normpath(os.path.join(dest, root))
        assert os.path.exists(droot)
        assert os.path.isdir(sroot)
        assert os.path.isdir(droot)
        for f in subfiles:
            sf, df = (os.path.join(sroot, f), os.path.join(droot, f))
            assert os.path.exists(df)
            assert os.path.isfile(sf)
            assert os.path.isfile(df)
            with open(sf, 'rb') as f:
                with open(df, 'rb') as g:
                    assert f.read() == g.read()

def test_files_upload_dir():
    files_upload_dir(dest="/tmp/__pytest_fora/")

def test_files_upload_dir_2():
    files_upload_dir(dest="/tmp/__pytest_fora/")

def test_files_upload_dir_rename():
    files_upload_dir(dest="/tmp/__pytest_fora/simple_inventory_renamed")

def test_files_upload_dir_rename_2():
    files_upload_dir(dest="/tmp/__pytest_fora/simple_inventory_renamed")

def test_full_deploy(request):
    os.chdir("test/simple_deploy")
    main(["inventory.py", "deploy.py"])
    os.chdir(request.config.invocation_dir)

def test_cleanup_directory():
    files.directory("/tmp/__pytest_fora", present=False)
    assert not os.path.exists("/tmp/__pytest_fora")

def test_close_connection():
    connection.__exit__(None, None, None)
    assert host.connection is None
