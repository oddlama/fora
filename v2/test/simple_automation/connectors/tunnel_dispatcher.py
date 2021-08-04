#!/usr/bin/env python3

"""
Provides a stdin/stdout based protocol to safely dispatch commands and return their
results over any connection that forwards both stdin/stdout.
"""

import os
import struct
import subprocess
import sys

from enum import IntEnum
from pwd import getpwnam, getpwuid
from grp import getgrnam, getgrgid
from struct import pack, unpack
from typing import cast, Any, TypeVar, Callable, Optional

T = TypeVar('T')

# TODO timeout
# TODO env

def resolve_umask(umask: str) -> int:
    """
    Resolves an octal string umask to a numeric umask.
    Raises a ValueError if the umask is malformed.

    Parameters
    ----------
    umask
        The string umask

    Returns
    -------
    int
        The numeric represenation of the umask
    """
    try:
        return int(umask, 8)
    except ValueError:
        raise ValueError(f"Invalid umask '{umask}': Must be in octal format.") # pylint: disable=raise-missing-from

def resolve_user(user: str) -> tuple[int, int]:
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
            pw = getpwuid(uid)
        except KeyError:
            raise ValueError(f"The user with the uid '{uid}' does not exist.") # pylint: disable=raise-missing-from
        except ValueError:
            raise ValueError(f"The user with the name '{user}' does not exist.") # pylint: disable=raise-missing-from

    return (pw.pw_uid, pw.pw_gid)

def resolve_group(group: str) -> int:
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
            gr = getgrgid(gid)
        except KeyError:
            raise ValueError(f"The group with the gid '{gid}' does not exist.") # pylint: disable=raise-missing-from
        except ValueError:
            raise ValueError(f"The group with the name '{group}' does not exist.") # pylint: disable=raise-missing-from

    return gr.gr_gid

# pylint: disable=too-many-public-methods
class Connection:
    """
    Represents a connection to this dispatcher via an input and output buffer.
    """

    def __init__(self, buffer_in, buffer_out):
        self.buffer_in = buffer_in
        self.buffer_out = buffer_out
        self.should_close = False

    def flush(self):
        """
        Flushes the output buffer.
        """
        self.buffer_out.flush()

    def read(self, count: int) -> bytes:
        """
        Reads a given number of bytes from the input buffer.

        Parameters
        ----------
        count: int
            The number of bytes to read from the input buffer

        Returns
        -------
        bytes
            The bytes from the input buffer
        """
        return self.buffer_in.read(count)

    def read_bytes(self) -> bytes:
        """
        Deserializes a bytes object from the input buffer.

        Returns
        -------
        bytes
            The deserialized object
        """
        return self.read(self.read_u64())

    def read_str(self) -> str:
        """
        Deserializes a str from the input buffer.

        Returns
        -------
        str
            The deserialized object
        """
        return self.read_bytes().decode('utf-8')

    def read_str_list(self) -> list[str]:
        """
        Deserializes a list of str from the input buffer.

        Returns
        -------
        list[str]
            The deserialized object
        """
        return list(self.read_str() for i in range(self.read_u64()))

    def _read_opt_generic(self, f: Callable[[], T]) -> Optional[T]:
        """
        Deserializes a generic optional object from the input buffer.

        Parameters
        ----------
        f
            The deserializing function for T

        Returns
        -------
        Optional[T]
            The deserialized object
        """
        return f() if self.read_bool() else None

    def read_opt_bytes(self) -> Optional[bytes]:
        """
        Deserializes a optional bytes object from the input buffer.

        Returns
        -------
        Optional[bytes]
            The deserialized object
        """
        return self._read_opt_generic(self.read_bytes)

    def read_opt_str(self) -> Optional[str]:
        """
        Deserializes a optional str from the input buffer.

        Returns
        -------
        Optional[str]
            The deserialized object
        """
        return self._read_opt_generic(self.read_str)

    def read_bool(self) -> bool:
        """
        Deserializes a bool from the input buffer.

        Returns
        -------
        bool
            The deserialized object
        """
        return cast(bool, unpack(">?", self.read(1))[0])

    def read_i32(self) -> int:
        """
        Deserializes a 32-bit signed integer from the input buffer.

        Returns
        -------
        int
            The deserialized object
        """
        return cast(int, unpack(">i", self.read(4))[0])

    def read_u32(self) -> int:
        """
        Deserializes a 32-bit unsigned integer from the input buffer.

        Returns
        -------
        int
            The deserialized object
        """
        return cast(int, unpack(">I", self.read(4))[0])

    def read_i64(self) -> int:
        """
        Deserializes a 64-bit signed integer from the input buffer.

        Returns
        -------
        int
            The deserialized object
        """
        return cast(int, unpack(">q", self.read(8))[0])

    def read_u64(self) -> int:
        """
        Deserializes a 64-bit unsigned integer from the input buffer.

        Returns
        -------
        int
            The deserialized object
        """
        return cast(int, unpack(">Q", self.read(8))[0])

    def write(self, data: bytes, count: int):
        """
        Writes a given number of bytes to the output buffer.

        Parameters
        ----------
        data
            The data bytes
        count
            The number of bytes to write
        """
        self.buffer_out.write(data[:count])

    def write_bytes(self, v: bytes):
        """
        Serializes a bytes object to the output buffer.

        Parameters
        ----------
        v
            The object to serialize
        """
        self.write(v, len(v))

    def write_str(self, v: str):
        """
        Serializes a str object to the output buffer.

        Parameters
        ----------
        v
            The object to serialize
        """
        self.write_bytes(v.encode('utf-8'))

    def write_str_list(self, v: list[str]):
        """
        Serializes a list of str to the output buffer.

        Parameters
        ----------
        v
            The object to serialize
        """
        self.write_u64(len(v))
        for i in v:
            self.write_str(i)

    def _write_opt_generic(self, v: Optional[T], f: Callable[[T], None]):
        """
        Serializes a generic optional to the output buffer.

        Parameters
        ----------
        v
            The object to serialize
        f
            The serializer function for T
        """
        self.write_bool(v is not None)
        if v is not None:
            f(v)

    def write_opt_bytes(self, v: Optional[bytes]):
        """
        Serializes an optional bytes object to the output buffer.

        Parameters
        ----------
        v
            The object to serialize
        """
        self._write_opt_generic(v, self.write_bytes)

    def write_opt_str(self, v: Optional[str]):
        """
        Serializes an optional str to the output buffer.

        Parameters
        ----------
        v
            The object to serialize
        """
        self._write_opt_generic(v, self.write_str)

    def write_bool(self, v: bool):
        """
        Serializes a bool to the output buffer.

        Parameters
        ----------
        v
            The object to serialize
        """
        self.write(pack(">?", v), 1)

    def write_i32(self, v: int):
        """
        Serializes a 32-bit signed integer to the output buffer.

        Parameters
        ----------
        v
            The object to serialize
        """
        self.write(pack(">i", v), 4)

    def write_u32(self, v: int):
        """
        Serializes a 32-bit unsigned integer to the output buffer.

        Parameters
        ----------
        v
            The object to serialize
        """
        self.write(pack(">I", v), 4)

    def write_i64(self, v: int):
        """
        Serializes a 64-bit signed integer to the output buffer.

        Parameters
        ----------
        v
            The object to serialize
        """
        self.write(pack(">q", v), 8)

    def write_u64(self, v: int):
        """
        Serializes a 64-bit unsigned integer to the output buffer.

        Parameters
        ----------
        v
            The object to serialize
        """
        self.write(pack(">Q", v), 8)

class Packets(IntEnum):
    """
    An enumeration type assigning an id to each packet.
    """
    ack = 0
    check_alive = 1
    exit = 2
    invalid_field = 3
    process_run = 4
    process_completed = 5
    process_preexec_error = 6

class PacketAck:
    """
    This packet is used to acknowledge the previous packet. Only
    sent on special occasions (e.g. PacketCheckAlive).
    """

    def write(self, conn: Connection):
        """
        Serializes the whole packet and writes it to the given connection.

        Parameters
        ----------
        conn
            The connection
        """
        _ = (self)
        conn.write_u32(Packets.ack)
        conn.flush()

    def handle(self, conn: Connection):
        """
        Handles this packet.

        Parameters
        ----------
        conn
            The connection
        """
        _ = (self, conn)

    @staticmethod
    def read(conn: Connection):
        """
        Deserializes a packet of this type from the given connection.

        Parameters
        ----------
        conn
            The connection
        """
        _ = (conn)
        return PacketAck()

class PacketCheckAlive:
    """
    This packet is used to check whether a connection is alive. The receiver must answer with
    PacketAck immediately.
    """

    def write(self, conn: Connection):
        """
        Serializes the whole packet and writes it to the given connection.

        Parameters
        ----------
        conn
            The connection
        """
        _ = (self)
        conn.write_u32(Packets.check_alive)
        conn.flush()

    def handle(self, conn: Connection):
        """
        Handles this packet.

        Parameters
        ----------
        conn
            The connection
        """
        _ = (self)
        PacketAck().write(conn)

    @staticmethod
    def read(conn: Connection):
        """
        Deserializes a packet of this type from the given connection.

        Parameters
        ----------
        conn
            The connection
        """
        _ = (conn)
        return PacketCheckAlive()

class PacketExit:
    """
    This packet is used to indicate that the dispatcher is no longer needed.
    """

    def write(self, conn: Connection):
        """
        Serializes the whole packet and writes it to the given connection.

        Parameters
        ----------
        conn
            The connection
        """
        _ = (self)
        conn.write_u32(Packets.exit)
        conn.flush()

    def handle(self, conn: Connection):
        """
        Handles this packet.

        Parameters
        ----------
        conn
            The connection
        """
        _ = (self)
        conn.should_close = True

    @staticmethod
    def read(conn: Connection):
        """
        Deserializes a packet of this type from the given connection.

        Parameters
        ----------
        conn
            The connection
        """
        _ = (conn)
        return PacketExit()

class PacketInvalidField:
    """
    This packet is used to indicate that an invalid value was passed to a field of a packet.
    """

    def __init__(self, field: str, error_message: str):
        self.field = field
        self.error_message = error_message

    def write(self, conn: Connection):
        """
        Serializes the whole packet and writes it to the given connection.

        Parameters
        ----------
        conn
            The connection
        """
        _ = (self)
        conn.write_u32(Packets.invalid_field)
        conn.write_str(self.field)
        conn.write_str(self.error_message)
        conn.flush()

    def handle(self, conn: Connection):
        """
        Handles this packet.

        Parameters
        ----------
        conn
            The connection
        """
        _ = (conn)
        raise ValueError(f"Invalid value given for field '{self.field}': {self.error_message}")

    @staticmethod
    def read(conn: Connection):
        """
        Deserializes a packet of this type from the given connection.

        Parameters
        ----------
        conn
            The connection
        """
        return PacketInvalidField(
            field=conn.read_str(),
            error_message=conn.read_str())

class PacketProcessRun:
    """
    This packet is used to start a new process.
    """

    def __init__(self, command: list[str],
                 stdin: Optional[bytes] = None,
                 capture_output: bool = True,
                 user: Optional[str] = None,
                 group: Optional[str] = None,
                 umask: Optional[str] = None,
                 cwd: Optional[str] = None):
        self.command = command
        self.stdin = stdin
        self.capture_output = capture_output
        self.user = user
        self.group = group
        self.umask = umask
        self.cwd = cwd

    def write(self, conn: Connection):
        """
        Serializes the whole packet and writes it to the given connection.

        Parameters
        ----------
        conn
            The connection
        """
        conn.write_u32(Packets.process_run)
        conn.write_str_list(self.command)
        conn.write_opt_bytes(self.stdin)
        conn.write_bool(self.capture_output)
        conn.write_opt_str(self.user)
        conn.write_opt_str(self.group)
        conn.write_opt_str(self.umask)
        conn.write_opt_str(self.cwd)
        conn.flush()

    def handle(self, conn: Connection):
        """
        Handles this packet.

        Parameters
        ----------
        conn
            The connection
        """
        # By default we will run commands as the current user.
        uid, gid = (None, None)
        umask_oct = 0o077

        if self.umask is not None:
            try:
                umask_oct = resolve_umask(self.umask)
            except ValueError as e:
                PacketInvalidField("umask", str(e)).write(conn)
                return

        if self.user is not None:
            try:
                (uid, gid) = resolve_user(self.user)
            except ValueError as e:
                PacketInvalidField("user", str(e)).write(conn)
                return

        if self.group is not None:
            try:
                gid = resolve_group(self.group)
            except ValueError as e:
                PacketInvalidField("group", str(e)).write(conn)
                return

        if self.cwd is not None:
            if not os.path.isdir(self.cwd):
                PacketInvalidField("cwd", "Requested working directory does not exist").write(conn)
                return

        def child_preexec():
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
            PacketProcessPreexecError().write(conn)
            return

        # Send response for command result
        PacketProcessCompleted(result.stdout, result.stderr, result.returncode).write(conn)

    @staticmethod
    def read(conn: Connection):
        """
        Deserializes a packet of this type from the given connection.

        Parameters
        ----------
        conn
            The connection
        """
        return PacketProcessRun(
            command=conn.read_str_list(),
            stdin=conn.read_opt_bytes(),
            capture_output=conn.read_bool(),
            user=conn.read_opt_str(),
            group=conn.read_opt_str(),
            umask=conn.read_opt_str(),
            cwd=conn.read_opt_str())

class PacketProcessCompleted:
    """
    This packet is used to return the results of a process.
    """

    def __init__(self,
                 stdout: Optional[bytes],
                 stderr: Optional[bytes],
                 returncode: int):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode

    def handle(self, conn: Connection):
        """
        Handles this packet.

        Parameters
        ----------
        conn
            The connection
        """
        _ = (self, conn)
        raise RuntimeError("This packet should never be sent by the client!")

    def write(self, conn: Connection):
        """
        Serializes the whole packet and writes it to the given connection.

        Parameters
        ----------
        conn
            The connection
        """
        conn.write_u32(Packets.process_completed)
        conn.write_opt_bytes(self.stdout)
        conn.write_opt_bytes(self.stderr)
        conn.write_i32(self.returncode)
        conn.flush()

    @staticmethod
    def read(conn: Connection):
        """
        Deserializes a packet of this type from the given connection.

        Parameters
        ----------
        conn
            The connection
        """
        return PacketProcessCompleted(
            stdout=conn.read_opt_bytes(),
            stderr=conn.read_opt_bytes(),
            returncode=conn.read_i32())

class PacketProcessPreexecError:
    """
    This packet is used to indicate an error in the preexec_fn when running the process.
    """

    def handle(self, conn: Connection):
        """
        Handles this packet.

        Parameters
        ----------
        conn
            The connection
        """
        _ = (self, conn)
        raise RuntimeError("This packet should never be sent by the client!")

    def write(self, conn: Connection):
        """
        Serializes the whole packet and writes it to the given connection.

        Parameters
        ----------
        conn
            The connection
        """
        _ = (self)
        conn.write_u32(Packets.process_preexec_error)
        conn.flush()

    @staticmethod
    def read(conn: Connection):
        """
        Deserializes a packet of this type from the given connection.

        Parameters
        ----------
        conn
            The connection
        """
        _ = (conn)
        return PacketProcessPreexecError()

packet_deserializers: dict[int, Callable[[Connection], Any]] = {
    Packets.ack: PacketAck.read,
    Packets.check_alive: PacketCheckAlive.read,
    Packets.exit: PacketExit.read,
    Packets.invalid_field: PacketInvalidField.read,
    Packets.process_run: PacketProcessRun.read,
    Packets.process_completed: PacketProcessCompleted.read,
    Packets.process_preexec_error: PacketProcessPreexecError.read,
}

def receive_packet(conn: Connection) -> Any:
    """
    Receives the next packet from the given connection.

    Parameters
    ----------
    conn
        The connection

    Returns
    -------
    Any
        The received packet
    """
    try:
        packet_id = conn.read_u32()
        if packet_id not in packet_deserializers:
            raise IOError(f"Received invalid packet id '{packet_id}'")

        return packet_deserializers[packet_id](conn)
    except struct.error as e:
        raise IOError("Unexpected EOF in data stream") from e

def main():
    """
    Handles all incoming packets in a loop until an invalid packet or a
    PacketExit is received.
    """
    conn = Connection(sys.stdin.buffer, sys.stdout.buffer)

    while not conn.should_close:
        try:
            packet = receive_packet(conn)
        except IOError as e:
            print(f"{str(e)}. Aborting.", file=sys.stderr, flush=True)
            sys.exit(3)
        packet.handle(conn)

if __name__ == '__main__':
    main()
