from pathlib import Path
import json,hashlib,re,importlib.util
ROOT=Path(__file__).resolve().parent
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def project_bytes(row):
 p=(ROOT/row['package_ref']).resolve();assert p.is_relative_to(ROOT.parents[1].resolve())
 b=p.read_bytes()
 if row['disposition']=='reuse_published_runtime_A':
  assert hashlib.sha256(b).hexdigest()==row['reference_sha256']
  if row['reference_transform']=='CRLF_to_LF':b=b.replace(b'\r\n',b'\n')
 assert hashlib.sha256(b).hexdigest()==row['export_sha256']
 return b
def verify():
 for row in read(ROOT/'PACKAGE_FILES.json'):
  b=(ROOT/row['path']).read_bytes();assert len(b)==row['bytes']and hashlib.sha256(b).hexdigest()==row['sha256'],row['path']
 spec=importlib.util.spec_from_file_location('runtime_A_verify',ROOT/'../20261104-a/verify_delivery.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);mod.verify()
 m=read(ROOT/'SOURCE_BINDING.json');assert m['native_inputs']==len(m['files'])==151
 assert len({r['path']for r in m['files']})==151
 projects=[r for r in m['files']if r['disposition']!='external_dependency_not_published']
 assert len(projects)==69 and sum(r['disposition']=='project_delta'for r in projects)==1
 for r in projects:project_bytes(r)
 top=project_bytes(next(r for r in projects if r['disposition']=='project_delta')).decode()
 assert re.search(r'parameter\s+CAMERA_RUNTIME_GAMMA\s*=\s*0',top)
 assert 'async_reg="true", PAP_ASYNC_REG=1'in top
 tables=read(ROOT/'STA_TABLES.json')['tables'];s=read(ROOT/'SUMMARY.json')
 assert set(tables)=={'slow','fast'}
 for corner,t in tables.items():
  assert set(t)=={'setup','hold','recovery','removal','skew','mpw'}
  for kind,v in t.items():
   r=v['rows'];a=v['summary']
   assert a['FailingEndpoints']==sum(x['failing_endpoints']for x in r)==0
   assert a['WNS_ns']==min(x['slack_ns']for x in r)>0
   assert a['WNS_ns']==s['internal_timing'][corner][kind]['WNS_ns']
 assert tables['slow']['setup']['summary']['WNS_ns']==0.016
 c=read(ROOT/'CONSTRAINT_REVIEW.json');assert c['actual_IO_check_counts']['no_input_delay']==55 and c['actual_IO_check_counts']['no_output_delay']==111
 assert not c['physical_reset_silicon_gate_CDC_MTBF_or_complete_external_IO_accepted']
 assert all(c['effective_RCF']['actual_route_success'].values())
 assert not s['frozen_bit_hash_only']['board_loaded']and not s['board60_accepted']
 assert not s['UART_Gamma_command_supported']
 return {'project_inputs':69,'new_top_source':1,'reused_project_sources':68,'dependencies_excluded':82,'internal_tables':12,'new_HDL_EDA_hardware':False}
if __name__=='__main__':print(json.dumps(verify()))
