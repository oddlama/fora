#!/usr/bin/env python3
# pylint: disable=too-many-lines

"""
Provides a stdin/stdout based protocol to safely dispatch commands and return their
results over any connection that forwards both stdin/stdout, as well as some other
needed remote system related utilities.
"""

import errno as sys_errno
import hashlib
import os
import stat
import struct
import subprocess
import sys
import typing

from pwd import getpwnam, getpwuid
from grp import getgrnam, getgrgid, getgrall
from spwd import getspnam
from struct import pack, unpack
from typing import IO, Any, Type, TypeVar, Callable, Optional, Union, NamedTuple, NewType, cast

T = TypeVar('T')
i32 = NewType('i32', int)
u32 = NewType('u32', int)
i64 = NewType('i64', int)
u64 = NewType('u64', int)

is_server = False
debug = False
try:
    from fora import globals as G
except ModuleNotFoundError:
    pass

# TODO: timeout on commands
# TODO: interactive commands?
# TODO: env

class RemoteOSError(Exception):
    """An exception type for remote OSErrors."""
    def __init__(self, errno: int, strerror: str, msg: str):
        super().__init__(msg)
        self.errno = errno
        self.strerror = strerror

# Utility functions
# ----------------------------------------------------------------

def _is_debug() -> bool:
    """Returns True if debugging output should be genereated."""
    return debug if is_server else cast(bool, G.args.debug)

def _log(msg: str) -> None:
    """
    Logs the given message to stderr, appending a prefix to indicate whether this
    is running on a remote (server) or locally (client).

    Parameters
    ----------
    msg
        The message to log.
    """
    if not _is_debug():
        return

    # TODO color should be configurable
    prefix = "  [1;33mREMOTE[m: " if is_server else "   [1;32mLOCAL[m: "
    print(f"{prefix}{msg}", file=sys.stderr, flush=True)

def _resolve_oct(value: str) -> int:
    """
    Resolves an octal string to a numeric value (e.g. for umask or mode).
    Raises a ValueError if the value is malformed.

    Parameters
    ----------
    value
        The octal string value

    Returns
    -------
    int
        The numeric representation of the octal value
    """
    try:
        return int(value, 8)
    except ValueError:
        raise ValueError(f"Invalid value '{value}': Must be in octal format.") # pylint: disable=raise-missing-from

def _resolve_user(user: str) -> tuple[int, int]:
    """
    Resolves the given user string to a uid and gid.
    The string may be either a username or a uid.
    Raises a ValueError if the user/uid does not exist.

    Parameters
    ----------
    user
        The username or uid to resolve

    Returns
    -------
    tuple[int, int]
        A tuple (uid, gid) with the numeric ids of the user and its primary group
    """
    try:
        pw = getpwnam(user)
    except KeyError:
        try:
            uid = int(user)
            try:
                pw = getpwuid(uid)
            except KeyError:
                raise ValueError(f"The user with the uid '{uid}' does not exist.") # pylint: disable=raise-missing-from
        except ValueError:
            raise ValueError(f"The user with the name '{user}' does not exist.") # pylint: disable=raise-missing-from

    return (pw.pw_uid, pw.pw_gid)

def _resolve_group(group: str) -> int:
    """
    Resolves the given group string to a gid.
    The string may be either a groupname or a gid.
    Raises a ValueError if the group/gid does not exist.

    Parameters
    ----------
    group
        The groupname or gid to resolve

    Returns
    -------
    int
        The numeric gid of the group
    """
    try:
        gr = getgrnam(group)
    except KeyError:
        try:
            gid = int(group)
            try:
                gr = getgrgid(gid)
            except KeyError:
                raise ValueError(f"The group with the gid '{gid}' does not exist.") # pylint: disable=raise-missing-from
        except ValueError:
            raise ValueError(f"The group with the name '{group}' does not exist.") # pylint: disable=raise-missing-from

    return gr.gr_gid

# Connection wrapper
# ----------------------------------------------------------------

# pylint: disable=too-many-public-methods
class Connection:
    """Represents a connection to this dispatcher via an input and output buffer."""

    def __init__(self, buffer_in: IO[bytes], buffer_out: IO[bytes]):
        self.buffer_in = buffer_in
        self.buffer_out = buffer_out
        self.should_close = False

    def flush(self) -> None:
        """Flushes the output buffer."""
        self.buffer_out.flush()

    def read(self, count: int) -> bytes:
        """Reads exactly the given amount of bytes."""
        return self.buffer_in.read(count)

    def write(self, data: bytes, count: int) -> None:
        """Writes exactly the given amount of bytes from data."""
        self.buffer_out.write(data[:count])

    def write_packet(self, packet: Any) -> None:
        """Writes the given packet."""
        if not hasattr(packet, '_is_packet') or not bool(getattr(packet, '_is_packet')):
            raise ValueError("Invalid argument: Must be a packet!")
        # We don't expose write directly, as the type checker currently is unable
        # to determine whether this function exists, as it is added by the @Packet decorator.
        packet._write(self) # pylint: disable=protected-access

# Primary serialization and deserialization
# ----------------------------------------------------------------

def _is_optional(field: Type[Any]) -> bool:
    """Returns True when the given type annotation is Optional[...]."""
    return typing.get_origin(field) is Union and type(None) in typing.get_args(field)

def _is_list(field: Type[Any]) -> bool:
    """Returns True when the given type annotation is list[...]."""
    return typing.get_origin(field) is list

_serializers: dict[Any, Callable[[Connection, Any], Any]] = {}
_serializers[bool]  = lambda conn, v: conn.write(pack(">?", v), 1)
_serializers[i32]   = lambda conn, v: conn.write(pack(">i", v), 4)
_serializers[u32]   = lambda conn, v: conn.write(pack(">I", v), 4)
_serializers[i64]   = lambda conn, v: conn.write(pack(">q", v), 8)
_serializers[u64]   = lambda conn, v: conn.write(pack(">Q", v), 8)
_serializers[bytes] = lambda conn, v: (_serializers[u64](conn, len(v)), conn.write(v, len(v))) # type: ignore[func-returns-value]
_serializers[str]   = lambda conn, v: _serializers[bytes](conn, v.encode('utf-8'))

def _serialize(conn: Connection, vtype: Type[Any], v: Any) -> None:
    """Serializes v based on the underlying type 'vtype' and writes it to the given connection."""
    if vtype in _serializers:
        _serializers[vtype](conn, v)
    elif _is_optional(vtype):
        real_type = typing.get_args(vtype)[0]
        _serializers[bool](conn, v is not None)
        if v is not None:
            _serialize(conn, real_type, v)
    elif _is_list(vtype):
        element_type = typing.get_args(vtype)[0]
        _serializers[u64](conn, len(v))
        for i in v:
            _serialize(conn, element_type, i)
    else:
        raise ValueError(f"Cannot serialize object of type {vtype}")

_deserializers: dict[Any, Callable[[Connection], Any]] = {}
_deserializers[bool]  = lambda conn: unpack(">?", conn.read(1))[0]
_deserializers[i32]   = lambda conn: unpack(">i", conn.read(4))[0]
_deserializers[u32]   = lambda conn: unpack(">I", conn.read(4))[0]
_deserializers[i64]   = lambda conn: unpack(">q", conn.read(8))[0]
_deserializers[u64]   = lambda conn: unpack(">Q", conn.read(8))[0]
_deserializers[bytes] = lambda conn: conn.read(_deserializers[u64](conn))
_deserializers[str]   = lambda conn: _deserializers[bytes](conn).decode('utf-8')

def _deserialize(conn: Connection, vtype: Type[Any]) -> Any:
    """Deserializes an object from the given connection based on the underlying type 'vtype' and returns it."""
    # pylint: disable=no-else-return
    if vtype in _deserializers:
        return _deserializers[vtype](conn)
    elif _is_optional(vtype):
        real_type = typing.get_args(vtype)[0]
        if not _deserializers[bool](conn):
            return None
        return _deserialize(conn, real_type)
    elif _is_list(vtype):
        element_type = typing.get_args(vtype)[0]
        return list(_deserialize(conn, element_type) for _ in range(_deserializers[u64](conn)))
    else:
        raise ValueError(f"Cannot deserialize object of type {vtype}")

# Packet helpers
# ----------------------------------------------------------------

packets: list[Any] = []
packet_deserializers: dict[int, Callable[[Connection], Any]] = {}

def _handle_response_packet() -> None:
    raise RuntimeError("This packet is a server-side response packet and must never be sent by the client!")

# Define generic read and write functions
def _read_packet(cls: Type[Any], conn: Connection) -> Any:
    kwargs: dict[str, Any] = {}
    for f in cast(Any, cls)._fields:
        ftype = cls.__annotations__[f]
        kwargs[f] = _deserialize(conn, ftype)
    return cls(**kwargs)

def _write_packet(cls: Type[Any], packet_id: u32, this: object, conn: Connection) -> None:
    _serialize(conn, u32, packet_id)
    for f in cls._fields:
        ftype = cls.__annotations__[f]
        _serialize(conn, ftype, getattr(this, f))
    conn.flush()

def Packet(type: str) -> Callable[[Type[Any]], Any]: # pylint: disable=redefined-builtin
    """Decorator for packet types. Registers the packet and generates read and write methods."""
    if type not in ['response', 'request']:
        raise RuntimeError("Invalid @Packet decoration: type must be either 'response' or 'request'.")

    def wrapper(cls: Type[Any]) -> Type[Any]:
        # Assert cls is a NamedTuple
        if not hasattr(cls, '_fields'):
            raise RuntimeError("Invalid @Packet decoration: Decorated class must inherit from NamedTuple.")

        # Find next packet id
        packet_id = u32(len(packets))

        # Replace functions
        cls._is_packet = True # pylint: disable=protected-access
        cls._write = lambda self, conn: _write_packet(cls, packet_id, self, conn) # pylint: disable=protected-access
        if type == 'response':
            cls.handle = _handle_response_packet
        elif type == 'request':
            if not hasattr(cls, 'handle') or not callable(getattr(cls, 'handle')):
                raise RuntimeError("Invalid @Packet decoration: request packets must provide a handle method!")

        # Register packet
        packets.append(cls)
        packet_deserializers[packet_id] = lambda conn: _read_packet(cls, conn)

        return cls
    return wrapper

# Packets
# ----------------------------------------------------------------

@Packet(type='response')
class PacketOk(NamedTuple):
    """This packet is used by some requests as a generic successful status indicator."""

@Packet(type='response')
class PacketAck(NamedTuple):
    """This packet is used to acknowledge a previous PacketCheckAlive packet."""

@Packet(type='request')
class PacketCheckAlive(NamedTuple):
    """This packet is used to check whether a connection is alive.
    The receiver must answer with PacketAck immediately."""

    def handle(self, conn: Connection) -> None:
        """Responds with PacketAck."""
        _ = (self)
        conn.write_packet(PacketAck())

@Packet(type='request')
class PacketExit(NamedTuple):
    """This packet is used to signal the server to close the connection and end the dispatcher."""
    def handle(self, conn: Connection) -> None:
        """Signals the connection to close."""
        _ = (self)
        conn.should_close = True

@Packet(type='response')
class PacketOSError(NamedTuple):
    """This packet is sent when an OSError occurs."""
    errno: i64
    strerror: str
    msg: str

@Packet(type='response')
class PacketInvalidField(NamedTuple):
    """This packet is used when an invalid value was given in a previous packet."""
    field: str
    error_message: str

@Packet(type='response')
class PacketProcessCompleted(NamedTuple):
    """This packet is used to return the results of a process."""
    stdout: Optional[bytes]
    stderr: Optional[bytes]
    returncode: i32

@Packet(type='response')
class PacketProcessError(NamedTuple):
    """This packet is used to indicate an error when running a process or when running the preexec_fn."""
    message: str

@Packet(type='request')
class PacketProcessRun(NamedTuple):
    """This packet is used to run a process."""
    command: list[str]
    stdin: Optional[bytes] = None
    capture_output: bool = True
    user: Optional[str] = None
    group: Optional[str] = None
    umask: Optional[str] = None
    cwd: Optional[str] = None

    def handle(self, conn: Connection) -> None:
        """Runs the requested command."""
        # By default we will run commands as the current user.
        uid, gid = (None, None)
        umask_oct = 0o077

        if self.umask is not None:
            try:
                umask_oct = _resolve_oct(self.umask)
            except ValueError as e:
                conn.write_packet(PacketInvalidField("umask", str(e)))
                return

        if self.user is not None:
            try:
                (uid, gid) = _resolve_user(self.user)
            except ValueError as e:
                conn.write_packet(PacketInvalidField("user", str(e)))
                return

        if self.group is not None:
            try:
                gid = _resolve_group(self.group)
            except ValueError as e:
                conn.write_packet(PacketInvalidField("group", str(e)))
                return

        if self.cwd is not None:
            if not os.path.isdir(self.cwd):
                conn.write_packet(PacketInvalidField("cwd", "The directory does not exist"))
                return

        def child_preexec() -> None:
            """
            Sets umask and becomes the correct user.
            """
            os.umask(umask_oct)
            if gid is not None:
                os.setresgid(gid, gid, gid)
            if uid is not None:
                os.setresuid(uid, uid, uid)
            if self.cwd is not None:
                os.chdir(self.cwd)

        # Execute command with desired parameters
        try:
            result = subprocess.run(self.command,
                input=self.stdin,
                capture_output=self.capture_output,
                cwd=self.cwd,
                preexec_fn=child_preexec,
                check=False)
        except subprocess.SubprocessError as e:
            conn.write_packet(PacketProcessError(str(e)))
            return

        # Send response for command result
        conn.write_packet(PacketProcessCompleted(result.stdout, result.stderr, i32(result.returncode)))

@Packet(type='response')
class PacketStatResult(NamedTuple):
    """This packet is used to return the results of a stat packet."""
    type: str # pylint: disable=redefined-builtin
    mode: u64
    owner: str
    group: str
    size: u64
    mtime: u64
    ctime: u64
    sha512sum: Optional[bytes]

@Packet(type='request')
class PacketStat(NamedTuple):
    """This packet is used to retrieve information about a file or directory."""
    path: str
    follow_links: bool = False
    sha512sum: bool = False

    def handle(self, conn: Connection) -> None:
        """Stats the requested path."""
        try:
            s = os.stat(self.path, follow_symlinks=self.follow_links)
        except OSError as e:
            if e.errno != sys_errno.ENOENT:
                raise
            conn.write_packet(PacketInvalidField("path", str(e)))
            return

        ftype = "dir"  if stat.S_ISDIR(s.st_mode)  else \
                "chr"  if stat.S_ISCHR(s.st_mode)  else \
                "blk"  if stat.S_ISBLK(s.st_mode)  else \
                "file" if stat.S_ISREG(s.st_mode)  else \
                "fifo" if stat.S_ISFIFO(s.st_mode) else \
                "link" if stat.S_ISLNK(s.st_mode)  else \
                "sock" if stat.S_ISSOCK(s.st_mode) else \
                "other"

        try:
            owner = getpwuid(s.st_uid).pw_name
        except KeyError:
            owner = str(s.st_uid)

        try:
            group = getgrgid(s.st_gid).gr_name
        except KeyError:
            group = str(s.st_gid)

        sha512sum: Optional[bytes]
        if self.sha512sum and ftype == "file":
            with open(self.path, 'rb') as f:
                sha512sum = hashlib.sha512(f.read()).digest()
        else:
            sha512sum = None

        # Send response
        conn.write_packet(PacketStatResult(
            type=ftype,
            mode=u64(stat.S_IMODE(s.st_mode)),
            owner=owner,
            group=group,
            size=u64(s.st_size),
            mtime=u64(s.st_mtime_ns),
            ctime=u64(s.st_ctime_ns),
            sha512sum=sha512sum))

@Packet(type='response')
class PacketResolveResult(NamedTuple):
    """This packet is used to return the results of a resolve packet."""
    value: str

@Packet(type='request')
class PacketResolveUser(NamedTuple):
    """
    This packet is used to canonicalize a user name / uid and to ensure it exists.
    If None is given, it queries the current user.
    """
    user: Optional[str]

    def handle(self, conn: Connection) -> None:
        """Resolves the requested user."""
        user = self.user if self.user is not None else str(os.getuid())

        try:
            pw = getpwnam(user)
        except KeyError:
            try:
                uid = int(user)
                pw = getpwuid(uid)
            except (KeyError, ValueError):
                conn.write_packet(PacketInvalidField("user", "The user does not exist"))
                return

        # Send response
        conn.write_packet(PacketResolveResult(value=pw.pw_name))

@Packet(type='request')
class PacketResolveGroup(NamedTuple):
    """
    This packet is used to canonicalize a group name / gid and to ensure it exists.
    If None is given, it queries the current group.
    """
    group: Optional[str]

    def handle(self, conn: Connection) -> None:
        """Resolves the requested group."""
        group = self.group if self.group is not None else str(os.getgid())

        try:
            gr = getgrnam(group)
        except KeyError:
            try:
                gid = int(group)
                gr = getgrgid(gid)
            except (KeyError, ValueError):
                conn.write_packet(PacketInvalidField("group", "The group does not exist"))
                return

        # Send response
        conn.write_packet(PacketResolveResult(value=gr.gr_name))

@Packet(type='request')
class PacketUpload(NamedTuple):
    """This packet is used to upload the given content to the remote and save it as a file.
    Responds with PacketOk if saving was successful, or PacketInvalidField if any
    field contained an invalid value."""
    file: str
    content: bytes
    mode: Optional[str] = None
    owner: Optional[str] = None
    group: Optional[str] = None

    def handle(self, conn: Connection) -> None:
        """Saves the content under the given path."""
        uid, gid = (None, None)
        mode_oct = 0o600

        if self.mode is not None:
            try:
                mode_oct = _resolve_oct(self.mode)
            except ValueError as e:
                conn.write_packet(PacketInvalidField("mode", str(e)))
                return

        if self.owner is not None:
            try:
                (uid, gid) = _resolve_user(self.owner)
            except ValueError as e:
                conn.write_packet(PacketInvalidField("owner", str(e)))
                return

        if self.group is not None:
            try:
                gid = _resolve_group(self.group)
            except ValueError as e:
                conn.write_packet(PacketInvalidField("group", str(e)))
                return

        with open(self.file, 'wb') as f:
            f.write(self.content)
        os.chmod(self.file, mode_oct)
        if uid is not None or gid is not None:
            os.chown(self.file, uid or 0, gid or 0)

        conn.write_packet(PacketOk())

@Packet(type='response')
class PacketDownloadResult(NamedTuple):
    """This packet is used to return the content of a file."""
    content: bytes

@Packet(type='request')
class PacketDownload(NamedTuple):
    """This packet is used to download the contents of a given file.
    Responds with PacketDownloadResult if reading was successful, or PacketInvalidField if any
    field contained an invalid value."""
    file: str

    def handle(self, conn: Connection) -> None:
        """Reads the file."""
        try:
            with open(self.file, 'rb') as f:
                content = f.read()
        except OSError as e:
            if e.errno != sys_errno.ENOENT:
                raise
            conn.write_packet(PacketInvalidField("file", str(e)))
            return

        conn.write_packet(PacketDownloadResult(content))

@Packet(type='response')
class PacketUserEntry(NamedTuple):
    """This packet is used to return information about a user."""
    name: str
    """The name of the user"""
    uid: i64
    """The numerical user id"""
    group: str
    """The name of the primary group"""
    gid: i64
    """The numerical primary group id"""
    groups: list[str]
    """All names of the supplementary groups this user belongs to"""
    password_hash: str
    """The password hash from shadow"""
    gecos: str
    """The comment (GECOS) field of the user"""
    home: str
    """The home directory of the user"""
    shell: str
    """The default shell of the user"""

@Packet(type='request')
class PacketQueryUser(NamedTuple):
    """This packet is used to get information about a group via pwd.getpw*."""
    user: str
    """User name or decimal uid"""

    def handle(self, conn: Connection) -> None:
        """Queries the requested user."""
        try:
            pw = getpwnam(self.user)
        except KeyError:
            try:
                gid = int(self.user)
                pw = getpwuid(gid)
            except (KeyError, ValueError):
                conn.write_packet(PacketInvalidField("user", "The user does not exist"))
                return

        try:
            pw_hash = getspnam(pw.pw_name).sp_pwdp
        except KeyError:
            conn.write_packet(PacketInvalidField("user", "The user has no shadow entry, or it is inaccessible."))
            return

        groups = [g.gr_name for g in getgrall() if pw.pw_name in g.gr_mem]
        try:
            conn.write_packet(PacketUserEntry(
                name=pw.pw_name,
                uid=i64(pw.pw_uid),
                group=getgrgid(pw.pw_gid).gr_name,
                gid=i64(pw.pw_gid),
                groups=groups,
                password_hash=pw_hash,
                gecos=pw.pw_gecos,
                home=pw.pw_dir,
                shell=pw.pw_shell))
        except KeyError:
            conn.write_packet(PacketInvalidField("user", "The user's primary group doesn't exist"))
            return

@Packet(type='response')
class PacketGroupEntry(NamedTuple):
    """This packet is used to return information about a group."""
    name: str
    """The name of the group"""
    gid: i64
    """The numerical group id"""
    members: list[str]
    """All the group member's user names"""

@Packet(type='request')
class PacketQueryGroup(NamedTuple):
    """This packet is used to get information about a group via grp.getgr*."""
    group: str
    """Group name or decimal gid"""

    def handle(self, conn: Connection) -> None:
        """Queries the requested group."""
        try:
            gr = getgrnam(self.group)
        except KeyError:
            try:
                gid = int(self.group)
                gr = getgrgid(gid)
            except (KeyError, ValueError):
                conn.write_packet(PacketInvalidField("group", "The group does not exist"))
                return

        # Send response
        conn.write_packet(PacketGroupEntry(name=gr.gr_name, gid=i64(gr.gr_gid), members=gr.gr_mem))

def receive_packet(conn: Connection, request: Any = None) -> Any:
    """
    Receives the next packet from the given connection.

    Parameters
    ----------
    conn
        The connection
    request
        The corresponding request packet, if any.

    Returns
    -------
    Any
        The received packet

    Raises
    ------
    RemoteOSError
        An OSError occurred on the remote host.
    IOError
        When an issue on the connection occurs.
    ValueError
        When an PacketInvalidField is received as the response and a corresponding request packet was given.
    """
    try:
        packet_id = cast(u32, _deserialize(conn, u32))
        if packet_id not in packet_deserializers:
            raise IOError(f"Received invalid packet id '{packet_id}'")

        try:
            packet_name = packets[packet_id].__name__
        except KeyError:
            packet_name = f"[unknown packet with id {packet_id}]"

        _log(f"got packet header for: {packet_name}")
        packet = packet_deserializers[packet_id](conn)
        if isinstance(packet, PacketOSError):
            raise RemoteOSError(msg=packet.msg, errno=packet.errno, strerror=packet.strerror)
        if isinstance(packet, PacketInvalidField):
            raise ValueError(f"invalid value '{getattr(request, packet.field)}' given for field '{packet.field}': {packet.error_message}")
        return packet
    except struct.error as e:
        raise IOError("Unexpected EOF in data stream") from e

def _main() -> None:
    """Handles all incoming packets in a loop until an invalid packet or a PacketExit is received."""
    os.umask(0o077)

    # pylint: disable=global-statement
    global debug
    global is_server
    debug = len(sys.argv) > 1 and sys.argv[1] == "--debug"
    is_server = __name__ == "__main__"

    conn = Connection(sys.stdin.buffer, sys.stdout.buffer)

    while not conn.should_close:
        try:
            _log("waiting for packet")
            packet = receive_packet(conn)
        except IOError as e:
            print(f"{str(e)}. Aborting.", file=sys.stderr, flush=True)
            sys.exit(3)
        _log(f"received packet {type(packet).__name__}")

        try:
            packet.handle(conn)
        except OSError as e:
            conn.write_packet(PacketOSError(errno=i64(e.errno), strerror=e.strerror, msg=str(e)))

if __name__ == '__main__':
    _main()
