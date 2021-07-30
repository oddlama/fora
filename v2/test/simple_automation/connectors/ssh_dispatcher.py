#!/usr/bin/env python3

"""
Provides a stdin/stdout based protocol to safely dispatch commands and return their
results over any connection that forwards both stdin/stdout.
"""

import sys
from enum import IntEnum
from struct import pack, unpack
from typing import cast, TypeVar, Callable, Optional

T = TypeVar('T')

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
        return f() if self.read_b() else None

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

    def read_b(self) -> bool:
        """
        Deserializes a bool from the input buffer.

        Returns
        -------
        bool
            The deserialized object
        """
        return cast(bool, unpack(">?", self.read(1)))

    def read_i32(self) -> int:
        """
        Deserializes a 32-bit signed integer from the input buffer.

        Returns
        -------
        int
            The deserialized object
        """
        return cast(int, unpack(">i", self.read(4)))

    def read_u32(self) -> int:
        """
        Deserializes a 32-bit unsigned integer from the input buffer.

        Returns
        -------
        int
            The deserialized object
        """
        return cast(int, unpack(">I", self.read(4)))

    def read_i64(self) -> int:
        """
        Deserializes a 64-bit signed integer from the input buffer.

        Returns
        -------
        int
            The deserialized object
        """
        return cast(int, unpack(">q", self.read(8)))

    def read_u64(self) -> int:
        """
        Deserializes a 64-bit unsigned integer from the input buffer.

        Returns
        -------
        int
            The deserialized object
        """
        return cast(int, unpack(">Q", self.read(8)))

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
        self.write_b(v is not None)
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

    def write_b(self, v: bool):
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
    exit = 0
    process_run = 1
    process_completed = 2

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

class PacketProcessRun:
    """
    This packet is used to start a new process.
    """

    def __init__(self, command: list[str],
                 stdin: Optional[bytes] = None,
                 stdout: Optional[bytes] = None,
                 user: Optional[str] = None,
                 group: Optional[str] = None,
                 umask: Optional[str] = None,
                 cwd: Optional[str] = None):
        self.command = command
        self.stdin = stdin
        self.stdout = stdout
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
        conn.write_opt_bytes(self.stdout)
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
        # TODO

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
            stdout=conn.read_opt_bytes(),
            user=conn.read_opt_str(),
            group=conn.read_opt_str(),
            umask=conn.read_opt_str(),
            cwd=conn.read_opt_str())

class PacketProcessCompleted:
    """
    This packet is used to return the results of a process.
    """

    def __init__(self,
                 stdout: bytes,
                 stderr: bytes,
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
        conn.write_bytes(self.stdout)
        conn.write_bytes(self.stderr)
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
            stdout=conn.read_bytes(),
            stderr=conn.read_bytes(),
            returncode=conn.read_i32())

packet_deserializers = {
    Packets.exit: PacketExit.read,
    Packets.process_run: PacketProcessRun.read,
    Packets.process_completed: PacketProcessCompleted.read,
}

def main():
    """
    Handles all incoming packets in a loop until an invalid packet or a
    PacketExit is received.
    """
    conn = Connection(sys.stdin.buffer, sys.stdout.buffer)

    while not conn.should_close:
        packet_id = conn.read_u32()
        if packet_id not in packet_deserializers:
            print(f"Received invalid packet id '{packet_id}'. Aborting.", file=sys.stderr, flush=True)
            sys.exit(3)

        packet = packet_deserializers[packet_id](conn)
        packet.handle(conn)

if __name__ == '__main__':
    main()
