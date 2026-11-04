from pathlib import Path
import json,hashlib,ast
ROOT=Path(__file__).resolve().parent
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def source_bytes(row):
 p=(ROOT/row['package_ref']).resolve();assert p.is_relative_to(ROOT.parents[2].resolve())
 b=p.read_bytes()
 if row['disposition']=='reuse_existing_project_source':
  assert hashlib.sha256(b).hexdigest()==row['reference_sha256']
  if row['reference_transform']=='CRLF_to_LF':b=b.replace(b'\r\n',b'\n')
 assert hashlib.sha256(b).hexdigest()==row['sha256']
 return b
def verify():
 for row in read(ROOT/'PACKAGE_FILES.json'):
  b=(ROOT/row['path']).read_bytes();assert len(b)==row['bytes']and hashlib.sha256(b).hexdigest()==row['sha256'],row['path']
 binding=read(ROOT/'SOURCE_BINDING.json');assert binding['actual_registered_designs']==8 and len(binding['projects'])==7
 for row in binding['projects']:source_bytes(row)
 assert len(read(ROOT/'FROZEN_NATIVE_ARCHIVE.json')['files'])==156
 s=read(ROOT/'SUMMARY.json');assert not s['board_loaded']and not s['real_DDR_latency_measured']and not s['actual_multi_outstanding_DDR_support_verified']
 assert s['probe_contract']['single_outstanding_only']and s['wire']['bytes']==80
 c=read(ROOT/'CONSTRAINT_REVIEW.json');assert c['external_IO_checks']['no_input_delay']==33 and c['external_IO_checks']['no_output_delay']==80
 assert not c['external_IO_reset_CDC_MTBF_signoff']
 for corner,t in read(ROOT/'STA_TABLES.json')['tables'].items():
  assert len(t)==6
  for kind,v in t.items():
   assert v['summary']['FailingEndpoints']==sum(x['failing_endpoints']for x in v['rows'])==0
   assert v['summary']['WNS_ns']==min(x['slack_ns']for x in v['rows'])==s['timing'][corner][kind]['WNS_ns']>0
 ast.parse((ROOT/'host/decode_pgddr.py').read_text(encoding='utf-8'))
 return {'project_RTL':7,'new_RTL':5,'reused_RTL':2,'internal_timing_tables':12,'parser_scope':'offline only','new_HDL_EDA_hardware':False}
if __name__=='__main__':print(json.dumps(verify()))
