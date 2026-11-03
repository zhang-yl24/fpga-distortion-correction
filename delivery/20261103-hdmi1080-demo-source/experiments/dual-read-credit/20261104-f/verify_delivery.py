from pathlib import Path
import json,hashlib,re
ROOT=Path(__file__).resolve().parent
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def extract_outer(b):
 lines=b.splitlines(keepends=True);start=next(i for i,x in enumerate(lines)if x.strip()==bytes([96])+b'ifdef EXPERIMENTAL_DUAL_READ_CREDIT');depth=0;split=end=None
 for i in range(start,len(lines)):
  m=re.match(rb'\s*\x60(ifdef|ifndef|else|endif|elsif)\b',lines[i])
  if not m:continue
  cmd=m.group(1)
  if cmd in [b'ifdef',b'ifndef']:depth+=1
  elif cmd==b'else'and depth==1:split=i
  elif cmd==b'elsif'and depth==1:raise AssertionError('Unexpected outer elsif')
  elif cmd==b'endif':
   depth-=1
   if depth==0:end=i;break
 assert split is not None and end is not None and not b''.join(lines[end+1:]).strip()
 return b''.join(lines[start+1:split]),b''.join(lines[split+1:end])
def legacy_reference(row):
 r=row['reference'];p=(ROOT/r['package_ref']).resolve();assert p.is_relative_to(ROOT.parents[2].resolve())
 b=p.read_bytes();assert hashlib.sha256(b).hexdigest()==r['reference_sha256']
 if r['reference_transform']=='CRLF_to_LF':b=b.replace(b'\r\n',b'\n')
 assert hashlib.sha256(b).hexdigest()==row['legacy_baseline_sha256']
 return b
def verify():
 for row in read(ROOT/'PACKAGE_FILES.json'):
  b=(ROOT/row['path']).read_bytes();assert len(b)==row['bytes']and hashlib.sha256(b).hexdigest()==row['sha256'],row['path']
 binding=read(ROOT/'SOURCE_BINDING.json');assert len(binding['rows'])==3 and not binding['default_macro_defined']
 for row in binding['rows']:
  b=(ROOT/row['package_ref']).read_bytes();assert hashlib.sha256(b).hexdigest()==row['authored_sha256']
  on,off=extract_outer(b);assert hashlib.sha256(on).hexdigest()==row['experimental_body_sha256']
  assert hashlib.sha256(off).hexdigest()==row['direct_legacy_branch_sha256']
  assert off==legacy_reference(row)+b'\n'
 s=read(ROOT/'SUMMARY.json');assert not s['full_frame_verified']and not s['vendor_ordered_two_accepted_reads_contract_verified']and not s['board_loaded']
 assert s['prefix_pixels']==131072 and s['queued_same_model_cycle_reduction']==11046
 assert [x['metrics']['core_ticks']for x in s['prefix']]==[143032,131986,145017]
 assert all(x['metrics']['full_frame']==0 and x['metrics']['done']==0 for x in s['prefix'])
 assert s['prefix_gamma_enable']==0
 ev=read(ROOT/'VERIFIED_EVIDENCE.json')['existing_real_xsim_runs'];assert len(ev)==8 and all(x['status']=='PASS_REAL_XSIM'and x['all_current_input_hashes_match']for x in ev)
 return {'guarded_modules':3,'prefix_pixels_only':131072,'same_model_cycles_saved':11046,'fullframe_or_board60_accepted':False,'new_HDL_EDA_hardware':False}
if __name__=='__main__':print(json.dumps(verify()))
