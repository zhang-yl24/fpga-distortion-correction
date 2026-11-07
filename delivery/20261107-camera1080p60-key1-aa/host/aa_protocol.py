"""Read-only AA wire parser / command-hex printer. No serial or device access.

Requires a known complete packet boundary, never searches through payload for
magic. Supports only the protocols actually enabled in frozen AA. Diagnostics
retain PGSTAT02 high24 fault-detail bits, unlike the legacy host decoder.
"""
from pathlib import Path
import argparse
import json
import struct
import zlib
from normal_function_uart import make_arm, decode as decode_b4
from stats_protocol_legacy import request as make_stats

def stats(packet):
 if len(packet)!=84 or packet[:8]!=b'PGSTAT02':raise ValueError('PGSTAT02 magic/length')
 if zlib.crc32(packet[:80])!=struct.unpack_from('<I',packet,80)[0]:raise ValueError('PGSTAT02 CRC')
 _,version,domain,size,ticket,nonce,valid,hz,seq,tick=struct.unpack_from('<8sBBHIIIIIQ',packet)
 if (version,domain,size)!=(2,1,84) or not ticket or not nonce or not hz or valid&~7 or valid&6!=6:raise ValueError('PGSTAT02 header/schema')
 keys=('last_process_cycles_raw','completed_frame_id','completed_param_id','completed_mode','captured_frames','processed_frames','presented_frames','scan_repeat_frames','dropped_frames','state_flags_raw')
 d=dict(zip(keys,struct.unpack_from('<10I',packet,40)))
 if d['completed_mode']&~3:raise ValueError('PGSTAT02 mode')
 if not valid&1 and any(d[k] for k in keys[:4]):raise ValueError('Invalid completion has nonzero data')
 flags=d['state_flags_raw']
 d.update(Magic='PGSTAT02',Ticket=ticket,Nonce=nonce,ValidMask=valid,NominalCoreHz=hz,Sequence=seq,CoreTick=tick,
  LastCompletionValid=bool(valid&1),StateFlagsLow8=flags&255,
  CoreFault=(flags>>8)&255,InputFault=(flags>>16)&255,ControllerFault=(flags>>24)&255,
  Failed=bool(flags&64),GammaEnabled=bool(d['completed_mode']&2),CorrectionEnabled=bool(d['completed_mode']&1),
  CRCValid=True,FullTimingOrHardwarePassClaim=False,ParamIDHex=f"{d['completed_param_id']:08x}")
 return d

def parse(data):
 result=[];pos=0
 while pos<len(data):
  if data[pos:pos+8] in (b'PGSTAT02',b'PGSIG001'):
   kind=data[pos:pos+8].decode();size=84 if kind=='PGSTAT02' else 128
  elif data[pos:pos+4]==b'SGK1':kind,size='SGK1',24
  else:raise ValueError(f'Unknown bytes at known packet boundary {pos}: {data[pos:pos+8].hex()}')
  packet=data[pos:pos+size]
  if len(packet)!=size:raise ValueError(f'Truncated {kind} at {pos}; raw capture must be retained')
  if kind=='PGSTAT02':decoded=stats(packet)
  else:
   acks,frames,bad=decode_b4(packet)
   rows=acks if kind=='SGK1' else frames
   if bad or len(rows)!=1 or not rows[0]['SchemaValid']:raise ValueError(f'Invalid {kind} at {pos}')
   decoded=rows[0]
   if kind=='PGSIG001':
    decoded['ExpectedAAParamID']=decoded['ParameterID']==0xadfb7264
    decoded['ExpectedAAMode']=decoded['Mode'] in (0,1)
    decoded['GammaExpectedOff']=not bool(decoded['Mode']&2)
    decoded['PixelGoldenCompared']=False
  result.append({'Offset':pos,'Kind':kind,'Decoded':decoded});pos+=size
 return result

def main():
 ap=argparse.ArgumentParser(description=__doc__);g=ap.add_mutually_exclusive_group(required=True)
 g.add_argument('--wire',type=Path);g.add_argument('--arm-hex',action='store_true');g.add_argument('--stats-hex',action='store_true')
 ap.add_argument('--ticket',type=lambda s:int(s,0));ap.add_argument('--nonce',type=lambda s:int(s,0));ap.add_argument('--known-packet-boundary',action='store_true')
 a=ap.parse_args()
 if a.wire:
  if not a.known_packet_boundary:ap.error('Capture must start at an externally known complete packet boundary; no resync is attempted')
  print(json.dumps({'Packets':parse(a.wire.read_bytes()),'SerialOpened':False,'HardwarePassClaim':False},indent=2));return
 if a.ticket is None or a.nonce is None:ap.error('--ticket and --nonce required')
 print((make_arm if a.arm_hex else make_stats)(a.ticket,a.nonce).hex())

if __name__=='__main__':main()
