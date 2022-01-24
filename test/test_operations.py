import grp
import inspect
import os
import pwd
import stat
from typing import cast

import pytest
from fora import utils

from fora.connection import Connection
from fora.main import main
from fora.operations import local, files, git, system
from fora.operations.api import OperationError
from fora.types import HostWrapper, HostWrapper, ScriptWrapper
import fora
import fora.loader

host: HostWrapper = cast(HostWrapper, None)
connection: Connection = cast(Connection, None)

def test_init():
    class DefaultArgs:
        debug = True
        diff = True
        dry = False
        changes = True
        verbose = 99
    fora.args = DefaultArgs()
    fora.loader.load_inventory("ssh://root@localhost")

    global host
    host = fora.inventory.loaded_hosts["localhost"]
    fora.host = host
    fora.script = ScriptWrapper("__internal_test")
    class Empty:
        pass
    fora.script.wrap(Empty())

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
    path = "/tmp/__pytest_fora"
    files.directory(path, present=False)

    # dry run create
    fora.args.dry = True
    ret = files.directory(path=path)
    assert ret.changed
    assert not os.path.isdir(path)
    fora.args.dry = False

    # create
    ret = files.directory(path=path)
    assert ret.changed
    assert os.path.isdir(path)

    # create unchanged
    ret = files.directory(path=path)
    assert not ret.changed
    assert os.path.isdir(path)

    # mode, owner, group
    ret = files.directory(path=path, mode="770", owner="nobody", group="nobody")
    s = os.stat(path)
    assert ret.changed
    assert stat.S_IMODE(s.st_mode) == 0o770
    assert s.st_uid == pwd.getpwnam("nobody").pw_gid
    assert s.st_gid == grp.getgrnam("nobody").gr_gid
    old_mtime = s.st_mtime

    # touch
    ret = files.directory(path=path, mode="770", owner="nobody", group="nobody", touch=True)
    s = os.stat(path)
    assert ret.changed
    assert stat.S_IMODE(s.st_mode) == 0o770
    assert s.st_uid == pwd.getpwnam("nobody").pw_gid
    assert s.st_gid == grp.getgrnam("nobody").gr_gid
    assert old_mtime < s.st_mtime

    # delete
    ret = files.directory(path=path, present=False)
    assert ret.changed
    assert not os.path.exists(path)

    # delete no-op
    ret = files.directory(path=path, present=False)
    assert not ret.changed
    assert not os.path.exists(path)

    # create for future tests as actual tmp folder
    ret = files.directory(path=path, mode="755", present=True)
    assert ret.changed
    assert os.path.isdir(path)

def test_files_file_wrong_existing_type():
    fora.args.dry = True
    with pytest.raises(OperationError, match="exists but is not a file"):
        files.file(path="/tmp/__pytest_fora")
    fora.args.dry = False

def test_invalid_path():
    with pytest.raises(ValueError, match="must be absolute"):
        files.directory(path="__tmp_fora")
    with pytest.raises(ValueError, match="must be non-empty"):
        files.directory(path="")
    with pytest.raises(ValueError, match="must be absolute"):
        files.file(path="__tmp_fora")
    with pytest.raises(ValueError, match="must be non-empty"):
        files.file(path="")
    with pytest.raises(ValueError, match="must be absolute"):
        files.link(path="__tmp_fora", target="__test")
    with pytest.raises(ValueError, match="must be non-empty"):
        files.link(path="", target="__test")
    with pytest.raises(ValueError, match="Link target cannot be empty"):
        files.link(path="/tmp/__tmp_fora_link", target="")

def test_files_file():
    path = "/tmp/__pytest_fora/testfile"

    # dry run create
    fora.args.dry = True
    ret = files.file(path=path)
    assert ret.changed
    assert not os.path.isfile(path)
    fora.args.dry = False

    # create
    ret = files.file(path=path)
    assert ret.changed
    assert os.path.isfile(path)

    # create unchanged
    ret = files.file(path=path)
    assert not ret.changed
    assert os.path.isfile(path)

    # mode, owner, group
    ret = files.file(path=path, mode="770", owner="nobody", group="nobody")
    s = os.stat(path)
    assert ret.changed
    assert stat.S_IMODE(s.st_mode) == 0o770
    assert s.st_uid == pwd.getpwnam("nobody").pw_gid
    assert s.st_gid == grp.getgrnam("nobody").gr_gid
    old_mtime = s.st_mtime

    # touch
    ret = files.file(path=path, mode="770", owner="nobody", group="nobody", touch=True)
    s = os.stat(path)
    assert ret.changed
    assert stat.S_IMODE(s.st_mode) == 0o770
    assert s.st_uid == pwd.getpwnam("nobody").pw_gid
    assert s.st_gid == grp.getgrnam("nobody").gr_gid
    assert old_mtime < s.st_mtime

    # delete
    ret = files.file(path=path, present=False)
    assert ret.changed
    assert not os.path.exists(path)

    # delete no-op
    ret = files.file(path=path, present=False)
    assert not ret.changed
    assert not os.path.exists(path)

    # create for future tests as actual file
    ret = files.file(path=path, mode="755", present=True)
    assert ret.changed
    assert os.path.isfile(path)

def test_files_dir_wrong_existing_type():
    fora.args.dry = True
    with pytest.raises(OperationError, match="exists but is not a directory"):
        files.directory(path="/tmp/__pytest_fora/testfile")
    fora.args.dry = False

def test_files_link_wrong_existing_type():
    fora.args.dry = True
    with pytest.raises(OperationError, match="exists but is not a link"):
        files.link(path="/tmp/__pytest_fora/testfile", target="/tmp/__pytest_fora/testfile")
    fora.args.dry = False

def test_files_link():
    path = "/tmp/__pytest_fora/testlink"
    target = "/tmp/__pytest_fora/testfile"

    # dry run create
    fora.args.dry = True
    ret = files.link(path=path, target=target)
    assert ret.changed
    assert not os.path.islink(path)
    fora.args.dry = False

    # create
    ret = files.link(path=path, target=target)
    assert ret.changed
    assert os.path.islink(path)
    assert os.path.realpath(path) == os.path.realpath(target)

    # create unchanged
    ret = files.link(path=path, target=target)
    assert not ret.changed
    assert os.path.islink(path)
    assert os.path.realpath(path) == os.path.realpath(target)

    # owner, group
    ret = files.link(path=path, target=target, owner="nobody", group="nobody")
    s = os.stat(path, follow_symlinks=False)
    assert ret.changed
    assert s.st_uid == pwd.getpwnam("nobody").pw_gid
    assert s.st_gid == grp.getgrnam("nobody").gr_gid
    old_mtime = s.st_mtime

    # touch
    ret = files.link(path=path, target=target, owner="nobody", group="nobody", touch=True)
    s = os.stat(path, follow_symlinks=False)
    assert ret.changed
    assert s.st_uid == pwd.getpwnam("nobody").pw_gid
    assert s.st_gid == grp.getgrnam("nobody").gr_gid
    assert old_mtime < s.st_mtime

    # delete
    ret = files.link(path=path, target=target, present=False)
    assert ret.changed
    assert not os.path.exists(path)

    # delete no-op
    ret = files.link(path=path, target=target, present=False)
    assert not ret.changed
    assert not os.path.exists(path)

    # create for future tests as actual link
    ret = files.link(path=path, target=target, present=True)
    assert ret.changed
    assert os.path.islink(path)
    assert os.path.realpath(path) == os.path.realpath(target)

def test_files_upload_content():
    content = os.urandom(512)

    # upload bytes
    fora.args.dry = True
    ret = files.upload_content(dest="/tmp/__pytest_fora/testcontent", content=content, mode="644")
    assert ret.changed
    assert not os.path.exists("/tmp/__pytest_fora/testcontent")
    fora.args.dry = False

    # upload bytes
    ret = files.upload_content(dest="/tmp/__pytest_fora/testcontent", content=content, mode="644")
    assert ret.changed
    with open("/tmp/__pytest_fora/testcontent", 'rb') as f:
        assert f.read() == content

    # upload bytes no-op
    ret = files.upload_content(dest="/tmp/__pytest_fora/testcontent", content=content, mode="644")
    assert not ret.changed
    with open("/tmp/__pytest_fora/testcontent", 'rb') as f:
        assert f.read() == content

    # upload bytes change only mode and owner
    ret = files.upload_content(dest="/tmp/__pytest_fora/testcontent", content=content, mode="604", owner="nobody")
    assert ret.changed
    with open("/tmp/__pytest_fora/testcontent", 'rb') as f:
        assert f.read() == content

    # upload str
    str_content = content.decode("ascii", errors='backslashreplace')
    ret = files.upload_content(dest="/tmp/__pytest_fora/testcontent", content=str_content, mode="644")
    assert ret.changed
    with open("/tmp/__pytest_fora/testcontent", 'rb') as f:
        assert f.read().decode('ascii', errors='ignore') == str_content

def test_files_upload_content_wrong_existing_type():
    fora.args.dry = True
    with pytest.raises(OperationError, match="exists but is not a file"):
        files.upload_content(dest="/tmp/__pytest_fora", content=b"")
    fora.args.dry = False

def test_files_upload():
    files.upload(src=__file__, dest="/tmp/__pytest_fora/testupload", mode="644")
    with open("/tmp/__pytest_fora/testupload", 'rb') as f:
        with open(__file__, 'rb') as g:
            assert f.read() == g.read()

def test_files_template_content():
    files.template_content(dest="/tmp/__pytest_fora/testtemplcontent", content="{{ myvar }}", context=dict(myvar="q948fhqh489f"), mode="644")
    with open("/tmp/__pytest_fora/testtemplcontent", 'rb') as f:
        assert f.read() == b"q948fhqh489f"

    with pytest.raises(ValueError, match="Error while templating"):
        files.template_content(dest="/tmp/__pytest_fora/testtemplcontent", content="{{ undefined_var }}", mode="644")

    # Test host override by trying to access .name which must not be overwritten.
    files.template_content(dest="/tmp/__pytest_fora/testtemplcontent", content="{{ host.name }}", context=dict(host=""), mode="644")

def test_files_template(request):
    files.template(src="test/templates/test.j2", dest="/tmp/__pytest_fora/testtempl", context=dict(myvar="graio208hfae"), mode="644")
    with open("/tmp/__pytest_fora/testtempl", 'rb') as f:
        assert f.read() == b"graio208hfae"

    try:
        with pytest.raises(ValueError, match="Error while templating"):
            os.chdir("test")
            files.template(src="../test/templates/test.j2", dest="/tmp/__pytest_fora/testtempl", mode="644")
    finally:
        os.chdir(request.config.invocation_dir)

    with pytest.raises(FileNotFoundError, match=r"No such file or directory"):
        files.template(src="test/templates/__nonexistent__.j2", dest="/tmp/__pytest_fora/testtempl", mode="644")

def test_files_upload_dir_invalid_src():
    with pytest.raises(ValueError, match="must be a directory"):
        files.upload_dir(src="test/simple_inventory/inventory.py",
                         dest="/tmp/__pytest_fora/simple_inventory_py_renamed",
                         dir_mode="755", file_mode="644")

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

def test_create_user():
    system.user(user="foratest", present=False)
    system.group(group="foratest", present=False)

    def getpwhash():
        ue = connection.query_user("foratest", query_password_hash=True)
        return ue.password_hash if ue is not None else None

    fora.args.dry = True
    ret = system.user(user="foratest")
    assert ret.changed
    with pytest.raises(KeyError):
        pwd.getpwnam("foratest")
    with pytest.raises(KeyError):
        grp.getgrnam("foratest")
    fora.args.dry = False

    ret = system.user(user="foratest")
    assert ret.changed
    pw = pwd.getpwnam("foratest")
    gr = grp.getgrgid(pw.pw_gid)
    assert gr.gr_name == "foratest"
    assert pw.pw_name == "foratest"
    assert pw.pw_gid == gr.gr_gid
    assert pw.pw_dir == "/dev/null"
    assert pw.pw_shell == "/sbin/nologin"
    assert pw.pw_gecos == ""
    assert getpwhash() == "!"

    ret = system.user(user="foratest")
    assert not ret.changed
    pw = pwd.getpwnam("foratest")
    gr = grp.getgrgid(pw.pw_gid)
    assert gr.gr_name == "foratest"
    assert pw.pw_name == "foratest"
    assert pw.pw_gid == gr.gr_gid
    assert pw.pw_dir == "/dev/null"
    assert pw.pw_shell == "/sbin/nologin"
    assert pw.pw_gecos == ""
    assert getpwhash() == "!"

    ret = system.user(user="foratest", present=False)
    assert ret.changed
    with pytest.raises(KeyError):
        pwd.getpwnam("foratest")
    with pytest.raises(KeyError):
        grp.getgrnam("foratest")

    ret = system.user(user="foratest", present=False)
    assert not ret.changed
    with pytest.raises(KeyError):
        pwd.getpwnam("foratest")
    with pytest.raises(KeyError):
        grp.getgrnam("foratest")

    ret = system.user(user="foratest", system=True)
    assert ret.changed
    pw = pwd.getpwnam("foratest")
    gr = grp.getgrgid(pw.pw_gid)
    assert gr.gr_name == "foratest"
    assert pw.pw_name == "foratest"
    assert pw.pw_gid == gr.gr_gid
    assert pw.pw_dir == "/dev/null"
    assert pw.pw_shell == "/sbin/nologin"
    assert pw.pw_gecos == ""
    assert getpwhash() == "!"

    ret = system.user(user="foratest", uid=12345, group="nobody", groups=["video"], append_groups=False, password_hash="!!", home="/", shell="/bin/bash", comment="some comment")
    assert ret.changed
    pw = pwd.getpwnam("foratest")
    gr = grp.getgrgid(pw.pw_gid)
    assert gr.gr_name == "nobody"
    groups = [g.gr_name for g in grp.getgrall() if pw.pw_name in g.gr_mem]
    assert pw.pw_name == "foratest"
    assert pw.pw_gid == gr.gr_gid
    assert pw.pw_uid == 12345
    assert pw.pw_dir == "/"
    assert pw.pw_shell == "/bin/bash"
    assert pw.pw_gecos == "some comment"
    assert getpwhash() == "!!"
    assert set(groups) == set(["video"])

    ret = system.user(user="foratest", groups=["audio"], append_groups=True)
    assert ret.changed
    pw = pwd.getpwnam("foratest")
    gr = grp.getgrgid(pw.pw_gid)
    assert gr.gr_name == "nobody"
    groups = [g.gr_name for g in grp.getgrall() if pw.pw_name in g.gr_mem]
    assert pw.pw_name == "foratest"
    assert pw.pw_uid == 12345
    assert pw.pw_dir == "/"
    assert pw.pw_shell == "/bin/bash"
    assert pw.pw_gecos == "some comment"
    assert getpwhash() == "!!"
    assert set(groups) == set(["video", "audio"])

    ret = system.user(user="foratest")
    assert not ret.changed
    pw = pwd.getpwnam("foratest")
    gr = grp.getgrgid(pw.pw_gid)
    assert gr.gr_name == "nobody"
    groups = [g.gr_name for g in grp.getgrall() if pw.pw_name in g.gr_mem]
    assert pw.pw_name == "foratest"
    assert pw.pw_uid == 12345
    assert pw.pw_dir == "/"
    assert pw.pw_shell == "/bin/bash"
    assert pw.pw_gecos == "some comment"
    assert getpwhash() == "!!"
    assert set(groups) == set(["video", "audio"])

    ret = system.user(user="foratest", present=False)
    assert ret.changed
    with pytest.raises(KeyError):
        pwd.getpwnam("foratest")
    gr = grp.getgrnam("foratest")
    assert gr.gr_name == "foratest"

    ret = system.user(user="foratest", uid=12345, group="foratest", groups=["nobody"], comment="abc", password_hash="!!")
    assert ret.changed
    pw = pwd.getpwnam("foratest")
    gr = grp.getgrgid(pw.pw_gid)
    assert gr.gr_name == "foratest"
    groups = [g.gr_name for g in grp.getgrall() if pw.pw_name in g.gr_mem]
    assert pw.pw_name == "foratest"
    assert pw.pw_uid == 12345
    assert pw.pw_dir == "/dev/null"
    assert pw.pw_shell == "/sbin/nologin"
    assert pw.pw_gecos == "abc"
    assert getpwhash() == "!!"
    assert set(groups) == set(["nobody"])

    with pytest.raises(ValueError, match="must be a list"):
        system.user(user="foratest", groups=cast(list[str], "oops_not_a_list"))

    ret = system.user(user="foratest", present=False)
    assert ret.changed
    with pytest.raises(KeyError):
        pwd.getpwnam("foratest")
    with pytest.raises(KeyError):
        grp.getgrnam("foratest")

def test_create_group():
    system.group(group="foratest", present=False)

    fora.args.dry = True
    ret = system.group(group="foratest")
    assert ret.changed
    with pytest.raises(KeyError):
        grp.getgrnam("foratest")
    fora.args.dry = False

    ret = system.group(group="foratest")
    assert ret.changed
    gr = grp.getgrnam("foratest")
    assert gr.gr_name == "foratest"

    ret = system.group(group="foratest")
    assert not ret.changed
    gr = grp.getgrnam("foratest")
    assert gr.gr_name == "foratest"

    ret = system.group(group="foratest", present=False)
    assert ret.changed
    with pytest.raises(KeyError):
        grp.getgrnam("foratest")

    ret = system.group(group="foratest", present=False)
    assert not ret.changed
    with pytest.raises(KeyError):
        grp.getgrnam("foratest")

    ret = system.group(group="foratest", system=True)
    assert ret.changed
    gr = grp.getgrnam("foratest")
    assert gr.gr_name == "foratest"

    ret = system.group(group="foratest", gid=12345)
    assert ret.changed
    gr = grp.getgrgid(12345)
    assert gr.gr_name == "foratest"

    ret = system.group(group="foratest")
    assert not ret.changed
    gr = grp.getgrnam("foratest")
    assert gr.gr_name == "foratest"

    ret = system.group(group="foratest", present=False)
    assert ret.changed
    with pytest.raises(KeyError):
        grp.getgrnam("foratest")

    ret = system.group(group="foratest", gid=12345)
    assert ret.changed
    gr = grp.getgrgid(12345)
    assert gr.gr_name == "foratest"

    ret = system.group(group="foratest", present=False)
    assert ret.changed
    with pytest.raises(KeyError):
        grp.getgrnam("foratest")

def test_files_line():
    files.upload_content(dest="/tmp/__pytest_fora/testcontent", content="  hello a \n  \t  hello b \n hello a\n", mode="644")

    fora.args.dry = True
    ret = files.line(path="/tmp/__pytest_fora/testcontent", line="hello c")
    assert ret.changed
    with open("/tmp/__pytest_fora/testcontent", 'rb') as f:
        assert b"hello c" not in f.read()
    fora.args.dry = False

    ret = files.line(path="/tmp/__pytest_fora/testcontent", line="hello c")
    assert ret.changed
    with open("/tmp/__pytest_fora/testcontent", 'rb') as f:
        assert b"hello c" in f.read()

    ret = files.line(path="/tmp/__pytest_fora/testcontent", line="hello c")
    assert not ret.changed
    with open("/tmp/__pytest_fora/testcontent", 'rb') as f:
        assert b"hello c" in f.read()

    ret = files.line(path="/tmp/__pytest_fora/testcontent", line="hello a", present=False)
    assert ret.changed
    with open("/tmp/__pytest_fora/testcontent", 'rb') as f:
        assert b"hello a" not in f.read()

    ret = files.line(path="/tmp/__pytest_fora/testcontent", line="hello b")
    assert not ret.changed
    with open("/tmp/__pytest_fora/testcontent", 'rb') as f:
        assert b"hello b" in f.read()

    ret = files.line(path="/tmp/__pytest_fora/testcontent", line=" hello d")
    assert ret.changed
    with open("/tmp/__pytest_fora/testcontent", 'rb') as f:
        assert b" hello d" in f.read()

    ret = files.line(path="/tmp/__pytest_fora/testcontent", line="hello d ", present=False, ignore_whitespace=False)
    assert not ret.changed
    with open("/tmp/__pytest_fora/testcontent", 'rb') as f:
        assert b"hello d " not in f.read()

    ret = files.line(path="/tmp/__pytest_fora/testcontent", line="hello d ", ignore_whitespace=False)
    assert ret.changed
    with open("/tmp/__pytest_fora/testcontent", 'rb') as f:
        assert b"hello d " in f.read()

    ret = files.line(path="/tmp/__pytest_fora/testcontent", line="hello\t \td")
    assert ret.changed
    with open("/tmp/__pytest_fora/testcontent", 'rb') as f:
        assert b"hello\t \td" in f.read()

    ret = files.line(path="/tmp/__pytest_fora/testcontent", line="<unused; remove hello d>", regex=r"hello\s+d", present=False)
    assert ret.changed
    with open("/tmp/__pytest_fora/testcontent", 'rb') as f:
        c = f.read()
        assert b"hello d" not in c
        assert b"hello\t \td" not in c

    ret = files.line(path="/tmp/__pytest_fora/testcontent", line="hello e", backup=True)
    assert ret.changed
    with open("/tmp/__pytest_fora/testcontent", 'rb') as f:
        assert b"hello e" in f.read()

    ret = files.line(path="/tmp/__pytest_fora/testcontent", line="hello e", present=False, backup="testcontent.withe")
    assert ret.changed
    with open("/tmp/__pytest_fora/testcontent", 'rb') as f:
        assert b"hello e" not in f.read()
    with open("/tmp/__pytest_fora/testcontent.withe", 'rb') as f:
        assert b"hello e" in f.read()

def test_files_line_wrong_existing_type():
    fora.args.dry = True
    with pytest.raises(OperationError, match="exists but is not a file"):
        files.line(path="/tmp/__pytest_fora", line="hello")
    fora.args.dry = False

def test_git_repo():
    fora.args.dry = True
    ret = git.repo(url="https://github.com/oddlama/fora", path="/tmp/__pytest_fora/gitrepo")
    assert ret.changed
    fora.args.dry = False

    ret = git.repo(url="https://github.com/oddlama/fora", path="/tmp/__pytest_fora/gitrepo")
    assert ret.changed

def test_full_deploy(request):
    os.chdir("test/simple_deploy")
    try:
        main(["inventory.py", "deploy.py"])
    finally:
        fora.host = host
        os.chdir(request.config.invocation_dir)

def test_full_deploy_inspect(request):
    os.chdir("test/simple_deploy")
    try:
        with pytest.raises(SystemExit):
            main(["--inspect-inventory", "inventory.py"])
    finally:
        fora.host = host
        os.chdir(request.config.invocation_dir)

def test_full_deploy_bad(request):
    os.chdir("test/simple_deploy")
    try:
        fora.args.debug = False
        with pytest.raises(ValueError, match="must be absolute"):
            main(["inventory.py", "deploy_bad.py"])
        fora.args.debug = True
    finally:
        fora.host = host
        os.chdir(request.config.invocation_dir)

def test_full_deploy_bad_recursive_test_script_traceback(request):
    os.chdir("test/simple_deploy")
    try:
        fora.args.debug = False
        with pytest.raises(ValueError, match="Invalid recursive call to") as e:
            main(["inventory.py", "deploy_bad_recursive.py"])
        utils.print_exception(e.type, e.value, e.tb)
        utils.script_trace([(cast(ScriptWrapper, None), inspect.getouterframes(inspect.currentframe())[0])], include_root=True)
        fora.args.debug = True
    finally:
        fora.host = host
        os.chdir(request.config.invocation_dir)

def test_cleanup_directory():
    files.directory("/tmp/__pytest_fora", present=False)
    assert not os.path.exists("/tmp/__pytest_fora")

def test_close_connection():
    connection.__exit__(None, None, None)
    assert host.connection is None
