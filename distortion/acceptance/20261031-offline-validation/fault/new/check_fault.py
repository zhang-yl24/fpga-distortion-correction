"""Independent file oracle from frozen synthetic pixels; never opens hardware."""
from pathlib import Path
import json,struct,zlib
from session_v3.host.control import AcquisitionGuard,Request,Ack,ABORTED,ARMED,decode_control
from session_v3.snapshot_b1.host.decoder import decode_packet
from session_v3.snapshot_b1.host.oracle import signature as golden_signature

NONCE_A=0x87654321;NONCE_B=0x76543210;TAG_B=0xa1000201
def rgb(p):
 r,g,b=p>>11,(p>>5)&63,p&31
 return bytes(((r<<3)|(r>>2),(g<<2)|(g>>4),(b<<3)|(b>>2)))
def pixels(root):
 a=[int(x,16) for x in (root/'vectors/expected1.mem').read_text().split()]
 assert len(a)==1024
 return a
def ack(status,ticket,nonce,epoch):
 b=struct.pack('<4sBBHIII',b'SGK1',1,status,24,ticket,nonce,epoch)
 return b+struct.pack('<I',zlib.crc32(b))
def expected_signature(root,epoch):
 values=pixels(root);b=bytearray(120);b[:8]=b'PGSIG001';b[8:12]=bytes((1,2,1,1))
 struct.pack_into('<HBB',b,12,128,8,0)
 struct.pack_into('<IIIIIIIIIIHH',b,16,NONCE_B,epoch,1,TAG_B,0,1024,
  zlib.crc32(b''.join(map(rgb,values))),0,0,0,32,32)
 b[60:64]=bytes((255,1,0,0))
 for i,(x,y) in enumerate(((0,0),(31,0),(0,31),(31,31),(16,16),(15,16),(16,15),(1,1))):
  struct.pack_into('<HH',b,64+7*i,x,y);b[68+7*i:71+7*i]=rgb(values[y*32+x])
 return bytes(b)+struct.pack('<I',zlib.crc32(b))+b'SG01'
class TestLedger:
 """CPU-only explicit challenges; not a replacement for real ledger persistence."""
 def __init__(self):self.next=0
 def reserve(self,randbits=None):
  self.next+=1
  return Request(self.next,NONCE_A if self.next==1 else NONCE_B)
def host_contract(root,epoch):
 expected=golden_signature(b''.join(map(rgb,pixels(root))),32,32)
 guard=AcquisitionGuard(TestLedger(),expected,param_id=TAG_B,mode=1)
 guard.begin(now=0)
 assert guard.accept_ack(Ack(1,NONCE_A,ABORTED,0),now=.1) is False
 assert guard.state=='FAILED' and guard.ack_epoch is None
 # A reset barrier must clear partial packet buffers, not just counters.
 guard.ack_stream.feed(ack(ARMED,1,NONCE_A,epoch)[:11])
 guard.record_stream.feed(expected_signature(root,epoch)[:51])
 guard.barrier('observed common reset after complete ABORTED ACK')
 guard.begin(now=.2)
 assert not guard.ack_stream.buffer and not guard.record_stream.buffer
 assert guard.accept_ack(Ack(1,NONCE_A,ARMED,epoch),now=.3) is False
 assert guard.state=='WAIT_ACK'
 record=decode_packet(expected_signature(root,epoch))
 from dataclasses import replace
 assert guard.accept_record(replace(record,session_id=NONCE_A),now=.3) is False
 assert guard.state=='WAIT_ACK'
 assert guard.accept_record(record,now=.3) is False and guard.state=='WAIT_ACK'
 assert guard.accept_ack(Ack(2,NONCE_B,ARMED,epoch),now=.4)
 assert guard.state=='WAIT_FRAME'
 assert guard.accept_record(record,now=.5) and guard.state=='VERIFIED'
 return {'old_ABO_ACK':'FAILED','reset_partial_buffers':'cleared','old_tuple':'ignored','new_record_before_ACK':'rejected','new_matching_ARMED_and_golden':'VERIFIED'}
def verify(root,work):
 lines=(work/'telemetry_trace.txt').read_text().splitlines()
 assert lines[-1]=='COMPLETE_FAULT_RECOVERY'
 assert lines.count('RESET_BARRIER')==1
 cut=lines.index('RESET_BARRIER')
 closes=[i for i,x in enumerate(lines) if x.startswith('FAULT_CLOSED ')]
 assert len(closes)==1 and closes[0]<cut
 closed=list(map(int,lines[closes[0]].split()[1:]));assert len(closed)==4
 assert closed[0:2]==[1,1] and min(closed[2:])>0
 rows=[x.split() for x in lines if x.startswith('P ')]
 assert len(rows)==1024
 epoch=int(rows[0][3]);assert epoch>0
 vals=pixels(root)
 for i,r in enumerate(rows):
  assert len(r)==12 and [int(r[1]),int(r[2]),int(r[3]),int(r[4]),int(r[5])]==[2,1,epoch,i%32,i//32]
  assert r[6].lower()==rgb(vals[i]).hex()
  assert [int(r[7]),int(r[8])]==[int(i==0),int(i==1023)]
  assert int(r[9],16)==TAG_B and int(r[10],16)==1 and int(r[11])==0
 assert not any(x.startswith('P ') for x in lines[:cut])
 wires={}
 for x in lines:
  if x.startswith('B '):assert len(x.split())==3 and x.split()[1] in ('1','2')
 for phase in (1,2):
  wires[phase]=bytes(int(x.split()[2],16) for x in lines if x.startswith(f'B {phase} '))
 assert wires[1]==ack(ABORTED,1,NONCE_A,0)
 assert wires[2]==ack(ARMED,2,NONCE_B,epoch)+expected_signature(root,epoch)
 assert len(wires[1])+len(wires[2])==176
 assert all(not x.startswith('B 2 ') for x in lines[:cut])
 assert all(not x.startswith('B 1 ') for x in lines[cut+1:])
 s=json.loads((work/'summary.json').read_text())
 for key,value in {'passed':True,'expected_underflows':1,'bad_done':1,'pending_abort_edges':1,'recovery_pixels':1024,'recovery_good':1,'wire_bytes':176,'acks':2,'signatures':1,'recovery_underflows':0,'physical_DDR':False}.items():assert s[key]==value,key
 assert s['recovery_crc565'].lower()==f'{zlib.crc32(struct.pack("<1024H",*vals)):08x}'
 assert s['fault_preconditions']==closed[2] and s['fault_hold_cycles']==closed[3]
 assert 'PASS FAULT_RECOVERY_REAL_SYSTEM' in (work/'simulate.log').read_text()
 return {'real_recovery_pixels':1024,'wire_bytes':176,'fault_signature_count':0,'recovery_signature_count':1,'host':host_contract(root,epoch),'HDL_required':True,'physical_DDR':False,'HardwareReleaseAllowed':False}
