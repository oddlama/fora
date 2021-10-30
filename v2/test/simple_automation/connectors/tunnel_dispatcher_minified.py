#!/usr/bin/env python3
import os
import stat
import struct
import subprocess
import sys
import typing
from enum import IntEnum
from pwd import getpwnam,getpwuid
from grp import getgrnam,getgrgid
from struct import pack,unpack
from typing import cast,Any,TypeVar,Callable,Optional,Union,NamedTuple,NewType
T=TypeVar('T')
i32=NewType('i32',int)
u32=NewType('u32',int)
i64=NewType('i64',int)
u64=NewType('u64',int)
is_server=False
debug=False
try:
 import simple_automation
except ModuleNotFoundError:
 pass
def is_debug():
 return debug if is_server else simple_automation.args.debug
def log(msg:str):
 if not is_debug():
  return
 prefix="  [1;33mREMOTE[m: " if is_server else "   [1;32mLOCAL[m: "
 print(f"{prefix}{msg}",file=sys.stderr,flush=True)
def resolve_umask(umask:str)->int:
 try:
  return int(umask,8)
 except ValueError:
  raise ValueError(f"Invalid umask '{umask}': Must be in octal format.")
def resolve_user(user:str)->tuple[int,int]:
 try:
  pw=getpwnam(user)
 except KeyError:
  try:
   uid=int(user)
   pw=getpwuid(uid)
  except KeyError:
   raise ValueError(f"The user with the uid '{uid}' does not exist.")
  except ValueError:
   raise ValueError(f"The user with the name '{user}' does not exist.")
 return(pw.pw_uid,pw.pw_gid)
def resolve_group(group:str)->int:
 try:
  gr=getgrnam(group)
 except KeyError:
  try:
   gid=int(group)
   gr=getgrgid(gid)
  except KeyError:
   raise ValueError(f"The group with the gid '{gid}' does not exist.")
  except ValueError:
   raise ValueError(f"The group with the name '{group}' does not exist.")
 return gr.gr_gid
class Connection:
 def __init__(self,buffer_in,buffer_out):
  self.buffer_in=buffer_in
  self.buffer_out=buffer_out
  self.should_close=False
 def flush(self):
  self.buffer_out.flush()
 def read(self,count:int)->bytes:
  return self.buffer_in.read(count)
 def write(self,data:bytes,count:int):
  self.buffer_out.write(data[:count])
 def write_packet(self,packet:Any):
  if not hasattr(packet,'_is_packet')or not bool(getattr(packet,'_is_packet')):
   raise ValueError("Invalid argument: Must be a packet!")
  packet._write(self)
def is_optional(field):
 return typing.get_origin(field)is Union and type(None)in typing.get_args(field)
def is_list(field):
 return typing.get_origin(field)is list
_serializers:dict[Any,Callable[[Connection,Any],Any]]={}
_serializers[bool]=lambda conn,v:conn.write(pack(">?",v),1)
_serializers[i32] =lambda conn,v:conn.write(pack(">i",v),4)
_serializers[u32] =lambda conn,v:conn.write(pack(">I",v),4)
_serializers[i64] =lambda conn,v:conn.write(pack(">q",v),8)
_serializers[u64] =lambda conn,v:conn.write(pack(">Q",v),8)
_serializers[bytes]=lambda conn,v:(_serializers[u64](conn,len(v)),conn.write(v,len(v)))
_serializers[str] =lambda conn,v:_serializers[bytes](conn,v.encode('utf-8'))
def serialize(conn:Connection,vtype,v:Any):
 if vtype in _serializers:
  _serializers[vtype](conn,v)
 elif is_optional(vtype):
  real_type=typing.get_args(vtype)[0]
  _serializers[bool](conn,v is not None)
  if v is not None:
   serialize(conn,real_type,v)
 elif is_list(vtype):
  element_type=typing.get_args(vtype)[0]
  _serializers[u64](conn,len(v))
  for i in v:
   serialize(conn,element_type,i)
 else:
  raise ValueError(f"Cannot serialize object of type {vtype}")
_deserializers:dict[Any,Callable[[Connection],Any]]={}
_deserializers[bool]=lambda conn:unpack(">?",conn.read(1))[0]
_deserializers[i32] =lambda conn:unpack(">i",conn.read(4))[0]
_deserializers[u32] =lambda conn:unpack(">I",conn.read(4))[0]
_deserializers[i64] =lambda conn:unpack(">q",conn.read(8))[0]
_deserializers[u64] =lambda conn:unpack(">Q",conn.read(8))[0]
_deserializers[bytes]=lambda conn:conn.read(_deserializers[u64](conn))
_deserializers[str] =lambda conn:_deserializers[bytes](conn).decode('utf-8')
def deserialize(conn:Connection,vtype):
 if vtype in _deserializers:
  return _deserializers[vtype](conn)
 elif is_optional(vtype):
  real_type=typing.get_args(vtype)[0]
  if not _deserializers[bool](conn):
   return None
  return deserialize(conn,real_type)
 elif is_list(vtype):
  element_type=typing.get_args(vtype)[0]
  return list(deserialize(conn,element_type)for i in range(_deserializers[u64](conn)))
 else:
  raise ValueError(f"Cannot deserialize object of type {vtype}")
class Packet:
 def write(self,conn:Connection):
  pass
 def handle(self,conn:Connection):
  pass
packets:list[Packet]=[]
packet_deserializers:dict[int,Callable[[Connection],Any]]={}
def _handle_response_packet():
 raise RuntimeError("This packet is a server-side response packet and must never be sent by the client!")
def _read_packet(cls,conn:Connection):
 kwargs={}
 for f in cls._fields:
  ftype=cls.__annotations__[f]
  kwargs[f]=deserialize(conn,ftype)
 return cls(**kwargs)
def _write_packet(cls,packet_id:u32,self,conn:Connection):
 serialize(conn,u32,packet_id)
 for f in cls._fields:
  ftype=cls.__annotations__[f]
  serialize(conn,ftype,getattr(self,f))
 conn.flush()
def packet(type):
 if type not in['response','request']:
  raise RuntimeError("Invalid @packet decoration: type must be either 'response' or 'request'.")
 def wrapper(cls):
  if not hasattr(cls,'_fields'):
   raise RuntimeError("Invalid @packet decoration: Decorated class must inherit from NamedTuple.")
  packet_id=len(packets)
  cls._is_packet=True
  cls._write=lambda self,conn:_write_packet(cls,packet_id,self,conn)
  if type=='response':
   cls.handle=_handle_response_packet
  elif type=='request':
   if not hasattr(cls,'handle')or not callable(getattr(cls,'handle')):
    raise RuntimeError("Invalid @packet decoration: request packets must provide a handle method!")
  packets.append(cls)
  packet_deserializers[packet_id]=lambda conn:_read_packet(cls,conn)
  return cls
 return wrapper
@packet(type='response')
class PacketAck(NamedTuple):
 pass 
@packet(type='request')
class PacketCheckAlive(NamedTuple):
 def handle(self,conn:Connection):
  _=(self)
  conn.write_packet(PacketAck())
@packet(type='request')
class PacketExit(NamedTuple):
 def handle(self,conn:Connection):
  _=(self)
  conn.should_close=True
@packet(type='response')
class PacketInvalidField(NamedTuple):
 field:str
 error_message:str
 def handle(self,conn:Connection):
  _=(conn)
  raise ValueError(f"Invalid value given for field '{self.field}': {self.error_message}")
@packet(type='request')
class PacketProcessRun(NamedTuple):
 command:list[str]
 stdin:Optional[bytes]=None
 capture_output:bool=True
 user:Optional[str]=None
 group:Optional[str]=None
 umask:Optional[str]=None
 cwd:Optional[str]=None
 def handle(self,conn:Connection):
  uid,gid=(None,None)
  umask_oct=0o077
  if self.umask is not None:
   try:
    umask_oct=resolve_umask(self.umask)
   except ValueError as e:
    conn.write_packet(PacketInvalidField("umask",str(e)))
    return
  if self.user is not None:
   try:
    (uid,gid)=resolve_user(self.user)
   except ValueError as e:
    conn.write_packet(PacketInvalidField("user",str(e)))
    return
  if self.group is not None:
   try:
    gid=resolve_group(self.group)
   except ValueError as e:
    conn.write_packet(PacketInvalidField("group",str(e)))
    return
  if self.cwd is not None:
   if not os.path.isdir(self.cwd):
    conn.write_packet(PacketInvalidField("cwd","Requested working directory does not exist"))
    return
  def child_preexec():
   os.umask(umask_oct)
   if gid is not None:
    os.setresgid(gid,gid,gid)
   if uid is not None:
    os.setresuid(uid,uid,uid)
   if self.cwd is not None:
    os.chdir(self.cwd)
  try:
   result=subprocess.run(self.command,input=self.stdin,capture_output=self.capture_output,cwd=self.cwd,preexec_fn=child_preexec,check=True)
  except subprocess.SubprocessError as e:
   conn.write_packet(PacketProcessPreexecError())
   return
  conn.write_packet(PacketProcessCompleted(result.stdout,result.stderr,i32(result.returncode)))
@packet(type='response')
class PacketProcessCompleted(NamedTuple):
 stdout:Optional[bytes]
 stderr:Optional[bytes]
 returncode:i32
@packet(type='response')
class PacketProcessPreexecError(NamedTuple):
 pass 
@packet(type='request')
class PacketStat(NamedTuple):
 path:str
 follow_links:bool=False
 def handle(self,conn:Connection):
  try:
   s=os.stat(self.path,follow_symlinks=self.follow_links)
  except OSError:
   conn.write_packet(PacketInvalidField("path","Path doesn't exist"))
   return
  ftype="dir" if stat.S_ISDIR(s.st_mode) else "chr" if stat.S_ISCHR(s.st_mode) else "blk" if stat.S_ISBLK(s.st_mode) else "file" if stat.S_ISREG(s.st_mode) else "fifo" if stat.S_ISFIFO(s.st_mode)else "link" if stat.S_ISLNK(s.st_mode) else "sock" if stat.S_ISSOCK(s.st_mode)else "other"
  try:
   owner=getpwuid(s.st_uid).pw_name
  except KeyError:
   owner=str(s.st_uid)
  try:
   group=getgrgid(s.st_gid).gr_name
  except KeyError:
   group=str(s.st_gid)
  conn.write_packet(PacketStatResult(type=ftype,mode=u64(stat.S_IMODE(s.st_mode)),owner=owner,group=group,size=u64(s.st_size),mtime=u64(s.st_mtime_ns),ctime=u64(s.st_ctime_ns)))
@packet(type='response')
class PacketStatResult(NamedTuple):
 type:str 
 mode:u64
 owner:str
 group:str
 size:u64
 mtime:u64
 ctime:u64
@packet(type='request')
class PacketResolveUser(NamedTuple):
 user:str
 def handle(self,conn:Connection):
  try:
   pw=getpwnam(self.user)
  except KeyError:
   try:
    uid=int(self.user)
    pw=getpwuid(uid)
   except(KeyError,ValueError):
    conn.write_packet(PacketInvalidField("user","The user does not exist"))
    return
  conn.write_packet(PacketResolveResult(value=pw.pw_name))
@packet(type='request')
class PacketResolveGroup(NamedTuple):
 group:str
 def handle(self,conn:Connection):
  try:
   gr=getgrnam(self.group)
  except KeyError:
   try:
    gid=int(self.group)
    gr=getgrgid(gid)
   except(KeyError,ValueError):
    conn.write_packet(PacketInvalidField("group","The group does not exist"))
    return
  conn.write_packet(PacketResolveResult(value=gr.gr_name))
@packet(type='response')
class PacketResolveResult(NamedTuple):
 value:str
def receive_packet(conn:Connection)->Any:
 try:
  packet_id=deserialize(conn,u32)
  if packet_id not in packet_deserializers:
   raise IOError(f"Received invalid packet id '{packet_id}'")
  try:
   packet_name=packets[packet_id].__name__
  except KeyError:
   packet_name=f"[unkown packet with id {packet_id}]"
  log(f"got packet header for: {packet_name}")
  return packet_deserializers[packet_id](conn)
 except struct.error as e:
  raise IOError("Unexpected EOF in data stream")from e
def main():
 global debug
 global is_server
 debug=len(sys.argv)>1 and sys.argv[1]=="--debug"
 is_server=__name__=="__main__"
 conn=Connection(sys.stdin.buffer,sys.stdout.buffer)
 while not conn.should_close:
  try:
   log("waiting for packet")
   packet=receive_packet(conn)
  except IOError as e:
   print(f"{str(e)}. Aborting.",file=sys.stderr,flush=True)
   sys.exit(3)
  log(f"received packet {type(packet).__name__}")
  packet.handle(conn)
if __name__=='__main__':
 main()
# Created by pyminifier (https://github.com/liftoff/pyminifier)
