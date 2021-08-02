#!/usr/bin/env python3
import sys
from enum import IntEnum
from struct import pack,unpack
from typing import cast,Any,TypeVar,Callable,Optional
T=TypeVar('T')
class Connection:
 def __init__(self,buffer_in,buffer_out):
  self.buffer_in=buffer_in
  self.buffer_out=buffer_out
  self.should_close=False
 def flush(self):
  self.buffer_out.flush()
 def read(self,count:int)->bytes:
  return self.buffer_in.read(count)
 def read_bytes(self)->bytes:
  return self.read(self.read_u64())
 def read_str(self)->str:
  return self.read_bytes().decode('utf-8')
 def read_str_list(self)->list[str]:
  return list(self.read_str()for i in range(self.read_u64()))
 def _read_opt_generic(self,f:Callable[[],T])->Optional[T]:
  return f()if self.read_b()else None
 def read_opt_bytes(self)->Optional[bytes]:
  return self._read_opt_generic(self.read_bytes)
 def read_opt_str(self)->Optional[str]:
  return self._read_opt_generic(self.read_str)
 def read_b(self)->bool:
  return cast(bool,unpack(">?",self.read(1)))
 def read_i32(self)->int:
  return cast(int,unpack(">i",self.read(4)))
 def read_u32(self)->int:
  return cast(int,unpack(">I",self.read(4)))
 def read_i64(self)->int:
  return cast(int,unpack(">q",self.read(8)))
 def read_u64(self)->int:
  return cast(int,unpack(">Q",self.read(8)))
 def write(self,data:bytes,count:int):
  self.buffer_out.write(data[:count])
 def write_bytes(self,v:bytes):
  self.write(v,len(v))
 def write_str(self,v:str):
  self.write_bytes(v.encode('utf-8'))
 def write_str_list(self,v:list[str]):
  self.write_u64(len(v))
  for i in v:
   self.write_str(i)
 def _write_opt_generic(self,v:Optional[T],f:Callable[[T],None]):
  self.write_b(v is not None)
  if v is not None:
   f(v)
 def write_opt_bytes(self,v:Optional[bytes]):
  self._write_opt_generic(v,self.write_bytes)
 def write_opt_str(self,v:Optional[str]):
  self._write_opt_generic(v,self.write_str)
 def write_b(self,v:bool):
  self.write(pack(">?",v),1)
 def write_i32(self,v:int):
  self.write(pack(">i",v),4)
 def write_u32(self,v:int):
  self.write(pack(">I",v),4)
 def write_i64(self,v:int):
  self.write(pack(">q",v),8)
 def write_u64(self,v:int):
  self.write(pack(">Q",v),8)
class Packets(IntEnum):
 ack=0
 check_alive=1
 exit=2
 process_run=3
 process_completed=4
class PacketAck:
 def write(self,conn:Connection):
  _=(self)
  conn.write_u32(Packets.ack)
  conn.flush()
 def handle(self,conn:Connection):
  _=(self,conn)
 @staticmethod
 def read(conn:Connection):
  _=(conn)
  return PacketAck()
class PacketCheckAlive:
 def write(self,conn:Connection):
  _=(self)
  conn.write_u32(Packets.check_alive)
  conn.flush()
 def handle(self,conn:Connection):
  _=(self)
  PacketAck().write(conn)
 @staticmethod
 def read(conn:Connection):
  _=(conn)
  return PacketCheckAlive()
class PacketExit:
 def write(self,conn:Connection):
  _=(self)
  conn.write_u32(Packets.exit)
  conn.flush()
 def handle(self,conn:Connection):
  _=(self)
  conn.should_close=True
 @staticmethod
 def read(conn:Connection):
  _=(conn)
  return PacketExit()
class PacketProcessRun:
 def __init__(self,command:list[str],stdin:Optional[bytes]=None,stdout:Optional[bytes]=None,user:Optional[str]=None,group:Optional[str]=None,umask:Optional[str]=None,cwd:Optional[str]=None):
  self.command=command
  self.stdin=stdin
  self.stdout=stdout
  self.user=user
  self.group=group
  self.umask=umask
  self.cwd=cwd
 def write(self,conn:Connection):
  conn.write_u32(Packets.process_run)
  conn.write_str_list(self.command)
  conn.write_opt_bytes(self.stdin)
  conn.write_opt_bytes(self.stdout)
  conn.write_opt_str(self.user)
  conn.write_opt_str(self.group)
  conn.write_opt_str(self.umask)
  conn.write_opt_str(self.cwd)
  conn.flush()
 def handle(self,conn:Connection):
  pass
 @staticmethod
 def read(conn:Connection):
  return PacketProcessRun(command=conn.read_str_list(),stdin=conn.read_opt_bytes(),stdout=conn.read_opt_bytes(),user=conn.read_opt_str(),group=conn.read_opt_str(),umask=conn.read_opt_str(),cwd=conn.read_opt_str())
class PacketProcessCompleted:
 def __init__(self,stdout:bytes,stderr:bytes,returncode:int):
  self.stdout=stdout
  self.stderr=stderr
  self.returncode=returncode
 def handle(self,conn:Connection):
  _=(self,conn)
  raise RuntimeError("This packet should never be sent by the client!")
 def write(self,conn:Connection):
  conn.write_u32(Packets.process_completed)
  conn.write_bytes(self.stdout)
  conn.write_bytes(self.stderr)
  conn.write_i32(self.returncode)
  conn.flush()
 @staticmethod
 def read(conn:Connection):
  return PacketProcessCompleted(stdout=conn.read_bytes(),stderr=conn.read_bytes(),returncode=conn.read_i32())
packet_deserializers={Packets.ack:PacketAck.read,Packets.check_alive:PacketCheckAlive.read,Packets.exit:PacketExit.read,Packets.process_run:PacketProcessRun.read,Packets.process_completed:PacketProcessCompleted.read,}
def receive_packet(conn:Connection)->Any:
 packet_id=conn.read_u32()
 if packet_id not in packet_deserializers:
  raise IOError(f"Received invalid packet id '{packet_id}'")
 return packet_deserializers[packet_id](conn)
def main():
 conn=Connection(sys.stdin.buffer,sys.stdout.buffer)
 while not conn.should_close:
  try:
   packet=receive_packet(conn)
  except IOError as e:
   print(f"{str(e)}. Aborting.",file=sys.stderr,flush=True)
   sys.exit(3)
  packet.handle(conn)
if __name__=='__main__':
 main()
# Created by pyminifier (https://github.com/liftoff/pyminifier)
