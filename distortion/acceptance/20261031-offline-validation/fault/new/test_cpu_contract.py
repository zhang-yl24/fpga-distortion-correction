from pathlib import Path
import tempfile,json,copy,struct,zlib
from check_fault import *
R=Path(__file__).resolve().parent
def fixture():
 vals=pixels(R);rows=[]
 rows.extend('B 1 %02x'%x for x in ack(ABORTED,1,NONCE_A,0))
 rows+=['FAULT_CLOSED 1 1 12 400','RESET_BARRIER']
 rows.extend('B 2 %02x'%x for x in ack(ARMED,2,NONCE_B,2)+expected_signature(R,2))
 for i,p in enumerate(vals):rows.append(f'P 2 1 2 {i%32} {i//32} {rgb(p).hex()} {int(i==0)} {int(i==1023)} {TAG_B:08x} 01 0')
 rows.append('COMPLETE_FAULT_RECOVERY')
 s={'passed':True,'expected_underflows':1,'bad_done':1,'pending_abort_edges':1,'fault_preconditions':12,'fault_hold_cycles':400,'recovery_pixels':1024,'recovery_good':1,'recovery_crc565':f'{zlib.crc32(struct.pack("<1024H",*vals)):08x}','wire_bytes':176,'acks':2,'signatures':1,'recovery_underflows':0,'physical_DDR':False}
 return rows,s
def check(rows,s):
 scratch=R/'.cpu-work';scratch.mkdir(exist_ok=True)
 assert scratch.resolve().is_relative_to(R.resolve())
 with tempfile.TemporaryDirectory(prefix='fault-oracle-cpu-',dir=scratch) as d:
  assert Path(d).resolve().is_relative_to(scratch.resolve())
  w=Path(d);(w/'telemetry_trace.txt').write_text('\n'.join(rows)+'\n');(w/'summary.json').write_text(json.dumps(s));(w/'simulate.log').write_text('PASS FAULT_RECOVERY_REAL_SYSTEM\n')
  return verify(R,w)
def main():
 rows,s=fixture();result=check(rows,s);negative=0
 def reject(rr,ss):
  nonlocal negative
  try:check(rr,ss)
  except (AssertionError,ValueError,KeyError):negative+=1;return
  raise AssertionError('mutation falsely accepted')
 for key,value in [('expected_underflows',0),('bad_done',0),('pending_abort_edges',0),('fault_preconditions',0),('recovery_pixels',1023),('recovery_good',0),('recovery_crc565','00000000'),('wire_bytes',175),('acks',1),('signatures',0),('recovery_underflows',1)]:
  q=dict(s);q[key]=value;reject(rows,q)
 for old,new in [('FAULT_CLOSED 1 1 12 400','FAULT_CLOSED 1 0 12 400'),('RESET_BARRIER','NO_RESET'),('COMPLETE_FAULT_RECOVERY','INCOMPLETE')]:reject([new if x==old else x for x in rows],s)
 first=next(i for i,x in enumerate(rows) if x.startswith('P '))
 for field,value in [(1,'1'),(2,'2'),(3,'0'),(4,'1'),(6,'000000'),(7,'0'),(9,'a1000101'),(10,'00'),(11,'1')]:
  rr=list(rows);q=rr[first].split();q[field]=value;rr[first]=' '.join(q);reject(rr,s)
 reject(rows[:first]+rows[first+1:],s)
 reject(['P 1 1 1 0 0 000000 1 0 a1000101 01 0']+rows,s)
 for at in [0,4,5,8,12,16,20]:
  rr=list(rows);rr[at]='B 1 %02x'%(int(rr[at].split()[2],16)^1);reject(rr,s)
 reject(rows[:-1]+['B 2 00',rows[-1]],s)
 reject(rows[:-1]+['B 3 00',rows[-1]],s)
 # Positive host tests are the unchanged actual control/decoder/oracle modules.
 host=host_contract(R,2)
 from dataclasses import replace
 def new_guard():
  g=AcquisitionGuard(TestLedger(),golden_signature(b''.join(map(rgb,pixels(R))),32,32),param_id=TAG_B,mode=1)
  g.begin(now=0);g.barrier('common reset');g.begin(now=.1);assert g.accept_ack(Ack(2,NONCE_B,ARMED,2),now=.2)
  return g
 record=decode_packet(expected_signature(R,2));host_negative=0
 for key,value in [('param_id',0xa1000101),('mode',0),('pixel_crc',0),('pixel_count',1023)]:
  g=new_guard()
  try:g.accept_record(replace(record,**{key:value}),now=.3)
  except ValueError:assert g.state=='FAILED';host_negative+=1
  else:raise AssertionError('real host accepted wrong golden/identity')
 g=new_guard();assert not g.accept_record(replace(record,scan_epoch=1),now=.3) and g.state=='WAIT_FRAME';host_negative+=1
 g=new_guard();assert g.accept_record(record,now=.3)
 try:g.accept_record(record,now=.4)
 except ValueError:assert g.state=='FAILED';host_negative+=1
 else:raise AssertionError('real host accepted duplicate sequence')
 damaged=bytearray(ack(ARMED,2,NONCE_B,2));damaged[-1]^=1
 try:decode_control(damaged,ack=True)
 except ValueError:host_negative+=1
 else:raise AssertionError('real host accepted corrupt ACK')
 return {'CPU_positive':True,'CPU_negative_mutations_rejected':negative,'real_host_negative_cases':host_negative,'host_contract':host,'HDL':'NOT_RUN','HardwareReleaseAllowed':False}
if __name__=='__main__':print(json.dumps(main(),indent=2))
