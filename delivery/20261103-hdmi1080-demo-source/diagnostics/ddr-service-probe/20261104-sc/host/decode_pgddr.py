"""Pure PGDDR001 decoder. No serial/device access on import."""
import re,struct,zlib
NAMES=['GroupCount','ARWaitMin','ARWaitMax','ARWaitSum','FirstRMin','FirstRMax','FirstRSum','LastRMin','LastRMax','LastRSum','ActualCRC','ExpectedCRC']
def decode_packet(p):
 if len(p)!=80 or p[:8]!=b'PGDDR001' or p[8:10]!=bytes([80,1]):raise ValueError('PGDDR001 schema')
 if zlib.crc32(p[:76])!=struct.unpack_from('<I',p,76)[0]:raise ValueError('PGDDR001 packet CRC')
 flags,seq=p[10:12];group=flags&3
 if group>2 or flags&128:raise ValueError('PGDDR001 flags')
 d={'Magic':'PGDDR001','Group':group,'Sequence':seq,'SnapshotValid':bool(flags&4),'KEY0':bool(flags&8),'GlobalResetN':bool(flags&16),'DDRInit':bool(flags&32),'DDRLock':bool(flags&64)}
 d.update(zip(['RefUptimeCycles','SnapshotCount','SnapshotAgeCycles'],struct.unpack_from('<3I',p,12)))
 d.update(zip(NAMES,struct.unpack_from('<12I',p,24)));s=struct.unpack_from('<I',p,72)[0]
 d.update(StatusRaw=s,Fault=s&255,Started=bool(s&256),Done=bool(s&512),Failed=bool(s&1024),CoreInit=bool(s&2048),Phase=(s>>12)&15,ActiveGroup=(s>>16)&3,WritesSaturated31=(s>>18)&31,ReadsSaturated63=(s>>23)&63,DataOrCRCError=bool(s&(1<<29)),ProtocolError=bool(s&(1<<30)),Timeout=bool(s&(1<<31)))
 d['Measured']=d['SnapshotValid'] and d['GroupCount']>0
 for prefix in ['ARWait','FirstR','LastR']:
  d[prefix+'MeanCycles']=d[prefix+'Sum']/d['GroupCount'] if d['Measured'] else None
 return d
def decode_stream(raw):
 packets=[];invalid=[]
 for m in re.finditer(b'PGDDR001',raw):
  p=raw[m.start():m.start()+80]
  try:d=decode_packet(p);d['Offset']=m.start();packets.append(d)
  except ValueError as e:invalid.append({'Offset':m.start(),'Reason':str(e)})
 return {'Packets':packets,'InvalidCandidates':invalid,'RawBytes':len(raw)}
