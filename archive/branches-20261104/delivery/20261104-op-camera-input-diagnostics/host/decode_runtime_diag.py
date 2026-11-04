import struct,zlib,json,argparse
from pathlib import Path
MAGIC=b'PGIQ0001';N=84
FLAG_NAMES=['selected_qualified','selected_failed','strict_qualified','strict_failed','observer_reset_n','observer_epoch_reset','startup_armed','pipeline_released','cfg_lock','video_lock','rx_done','tx_done','ddr_ready','global_reset_n','ref_reset','board_failed','system_failed','hard_overlap','polarity_known','source_fault_valid','ref_fault_valid','snapshot_seen','timing_detail_valid','source_domain_reset_n']
REASON_NAMES=['geometry_disabled','geometry_ref_reset','geometry_failed','source_unhealthy','held_snapshot_unhealthy','no_good_frame','pclk_stale','vs_stale','de_stale','frame_stale','snapshot_stale','source_failed_sync','held_source_fault_valid','ref_fault_valid','held_source_fault_code','reserved15','status_ref_reset','polarity_unknown','fewer_than_two_good_frames','rate_unseen','rate_bad','geometry_failed_status','rate_failed_sticky','hard_overlap','strict_timing_failed','strict_timing_unseen','strict_failed','functional_failed','strict_unqualified','functional_unqualified']
def tuple_decode(buf):
 w=struct.unpack('<8I',buf);f=w[1];r=w[2]
 return {'ref_tick':w[0],'flags_hex':f'{f:08x}','flags':{n:bool(f>>i&1) for i,n in enumerate(FLAG_NAMES)},'reason_hex':f'{r:08x}','reasons':[n for i,n in enumerate(REASON_NAMES) if r>>i&1],'pclk_edges_per_window':w[3],'good_frames':w[4],'bad_frames':w[5],'last_pixels_per_line':w[6]&65535,'last_lines':w[6]>>16,'board_fault':f'{w[7]>>24:02x}','input_fault':f'{w[7]>>16&255:02x}','ref_fault':f'{w[7]>>8&255:02x}','source_fault':f'{w[7]&255:02x}','raw_words':list(w)}
def decode(data):
 packets=[];errors=[];pos=0
 while pos<len(data):
  k=data.find(MAGIC,pos)
  if k<0:
   if pos<len(data):errors.append({'offset':pos,'error':'trailing_or_unrecognized_bytes'})
   break
  if k>pos:errors.append({'offset':pos,'error':'unrecognized_prefix','bytes':k-pos})
  if len(data)-k<N:errors.append({'offset':k,'error':'partial_packet'});break
  p=data[k:k+N];pos=k+N
  if p[9]!=N or p[8]&248 or p[10:12]!=b'\0\0':errors.append({'offset':k,'error':'header'});continue
  if p[8]&2 and not p[8]&1:errors.append({'offset':k,'error':'follow_without_first'});continue
  if zlib.crc32(p[:80])!=int.from_bytes(p[80:84],'little'):errors.append({'offset':k,'error':'CRC'});continue
  packets.append({'sequence':int.from_bytes(p[12:16],'little'),'first_valid':bool(p[8]&1),'follow_valid':bool(p[8]&2),'uptime_has_wrapped':bool(p[8]&4),'first_or_live':tuple_decode(p[16:48]),'follow_or_live':tuple_decode(p[48:80])})
 return {'schema_version':1,'scope':'27MHz_input_qualification_diagnostic_only','packets':packets,'errors':errors,'camera_fix_proven':False,'board_test_proven':False}
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('wire',type=Path);a.add_argument('--out',type=Path);x=a.parse_args();d=decode(x.wire.read_bytes());s=json.dumps(d,indent=2)+'\n'
 if x.out:x.out.write_text(s,encoding='utf-8')
 print(s);raise SystemExit(0 if d['packets'] and not d['errors'] else 2)
