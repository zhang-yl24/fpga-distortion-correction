"""Independent stdlib oracle: immutable pre-existing pixel vectors -> UART packets.
Does not derive expected values from captured DUT CRC/data or accept mere exit0.
"""
from pathlib import Path
import json,struct,zlib,sys
def rgb(p):
 r,g,b=p>>11,(p>>5)&63,p&31
 return bytes(((r<<3)|(r>>2),(g<<2)|(g>>4),(b<<3)|(b>>2)))
def expected_pixels(root,f):
 return [int(x,16) for x in (root/'vectors'/('expected1.mem' if f==2 else 'expected0.mem')).read_text().split()]
def signature(root,f,epoch):
 values=expected_pixels(root,f);assert len(values)==1024
 b=bytearray(120);b[:8]=b'PGSIG001';b[8:12]=bytes((1,2,1,1))
 struct.pack_into('<HBB',b,12,128,8,(f-1)%2)
 struct.pack_into('<IIIIIIIIIIHH',b,16,0x87654321,epoch,f,0xa1000000+f,f-1,1024,
                  zlib.crc32(b''.join(map(rgb,values))),0,0,0,32,32)
 b[60:64]=bytes((255,int(f==2),0,0))
 coords=((0,0),(31,0),(0,31),(31,31),(16,16),(15,16),(16,15),(1,1))
 for i,(x,y) in enumerate(coords):
  struct.pack_into('<HH',b,64+7*i,x,y);b[68+7*i:71+7*i]=rgb(values[y*32+x])
 return bytes(b)+struct.pack('<I',zlib.crc32(b))+b'SG01'
def verify(root,work):
 lines=(work/'telemetry_trace.txt').read_text().splitlines()
 assert lines[-1]=='COMPLETE_REAL_SYSTEM_TELEMETRY'
 epochs={}
 for f in (1,2,3):
  rows=[x.split() for x in lines if x.startswith(f'P {f} ')]
  assert len(rows)==1024,(f,len(rows));epochs[f]=int(rows[0][2]);assert epochs[f]>0
  expected=expected_pixels(root,f)
  for i,r in enumerate(rows):
   assert [int(r[2]),int(r[3]),int(r[4])]==[epochs[f],i%32,i//32]
   assert r[5].lower()==rgb(expected[i]).hex()
   assert [int(r[6]),int(r[7])]==[int(i==0),int(i==1023)]
   assert int(r[8],16)==0xa1000000+f and int(r[9],16)==int(f==2)
   assert int(r[10])==(f-1)%2
 raw=bytes(int(x.split()[1],16) for x in lines if x.startswith('B '))
 footer=next(x.split() for x in lines if x.startswith('T '));assert int(footer[1])==len(raw)
 pos=0;ack=0;frames=[]
 while pos<len(raw):
  if raw[pos:pos+4]==b'SGK1':
   a=b'SGK1'+bytes((1,1))+struct.pack('<HIII',24,1,0x87654321,epochs[1])
   assert raw[pos:pos+24]==a+struct.pack('<I',zlib.crc32(a));ack+=1;pos+=24
  else:
   assert raw[pos:pos+8]==b'PGSIG001'
   f=struct.unpack_from('<I',raw,pos+24)[0];assert f in epochs and f not in frames
   assert raw[pos:pos+128]==signature(root,f,epochs[f]),f
   frames.append(f);pos+=128
 assert ack==1 and frames==sorted(frames) and 1 in frames and 2 in frames
 assert int(footer[2])==3-len(frames),'telemetry drop accounting != unreported completed scans'
 s=json.loads((work/'summary.json').read_text());assert s['passed'] and s['total_scanned_pixels']==3072
 assert s['underflows']==s['crc_mismatches']==s['dropped_frames']==s['overflow_frames']==s['no_free_frames']==0
 assert s['legacy_collision_injection'] is False
 for key in ('forced_result_aw_hold_cycles','forced_display_ar_hold_cycles','forced_write_dual_clients_seen','forced_read_dual_clients_seen'):
  assert s[key]==0,key
 return {'collision_injection':'NOT_RUN_IN_NORMAL_READBACK_PHASE',
 'observed_read_contention':s['read_contention'],'observed_write_contention':s['write_contention'],
 'real_system_pixels':3072,'wire_bytes':len(raw),'signature_frames':frames,
 'signature_dropped':int(footer[2]),'corrected_frame_wire_verified':True,'hardware_proven':False}
if __name__=='__main__':
 r=Path(__file__).resolve().parent;print(json.dumps(verify(r,Path(sys.argv[1]).resolve()),indent=2))
