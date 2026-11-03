"""Audit the optional exact DDR CA net attribute and synthesized LUT replicas.

This is a local Boolean equivalence check, not a whole-chip formal proof or a
claim that the final placed net has at most 16 loads. No project is modified.
"""
from pathlib import Path
import argparse, hashlib, json, re, xml.etree.ElementTree as ET

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--project',type=Path,required=True);p.add_argument('--reference-project',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 root=a.project;plan_path=root/'candidate-plan.json';plan=json.loads(plan_path.read_text());checks=[];extra_evidence=[]
 def check(name,ok,detail=None):checks.append(dict(name=name,pass_=bool(ok),detail=detail))
 fdc=root/'compiled/board/ddr-ca-maxfan16.fdc';expected='define_attribute {n:u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/all_group_ca_dly} {syn_maxfan} {16}'
 cmds=[s.strip() for s in fdc.read_text().splitlines() if s.strip() and not s.lstrip().startswith('#')]
 check('exact_single_net_synthesis_attribute',cmds==[expected],cmds)
 pds=root/'hdmi_camera_fisheye_top.pds';items=ET.parse(pds).getroot().findall('.//inputs/item')
 check('native_pds_registered_fdc',any((root/i.get('file','')).resolve()==fdc.resolve() and i.get('format')=='fdc' for i in items))
 ccr=root/'prj_tasks/syn_1/synthesize/constraint_check.ccr';ccr_text=ccr.read_text();check('synthesis_loaded_constraint_without_errors',str(fdc).replace('\\','/') in ccr_text and 'Found 0 error(s), 0 critical warning(s)' in ccr_text)
 vm=root/'prj_tasks/syn_1/synthesize/hdmi_camera_fisheye_top_syn.vm';text=vm.read_text();gates=[]
 for match in re.finditer(r"GTP_LUT4\s*#\(\s*\.INIT\(16'h([0-9A-Fa-f]+)\)\)\s+(\S+)\s*\((.*?)\);",text,re.S):
  ports=dict(re.findall(r'\.(\w+)\s*\(([^()]*)\)',match[3]));net=ports.get('Z','').strip()
  if re.fullmatch(r'all_group_ca_dly(?:_\d+)?',net):gates.append(dict(instance=match[2],output=net,init=match[1].upper(),inputs=[ports.get('I'+str(i),'').strip() for i in range(4)]))
 expected_inputs=['debug_data[66]','debug_data[135]','debug_data[204]','debug_data[273]']
 check('replicated_exact_combinational_driver',len(gates)>=2 and all(g['init']=='FFFE' and g['inputs']==expected_inputs for g in gates),gates)
 attrs=re.findall(r'\(\*\s*PAP_MAX_FANOUT=16\s*\*\)\s*wire\s+(all_group_ca_dly(?:_\d+)?)\s*;',text)
 check('native_attribute_survives_synthesis',bool(gates) and {g['output'] for g in gates}<=set(attrs),attrs)
 truths=[int(g['init'],16) for g in gates]
 check('all_16_input_assignments_equivalent',bool(truths) and all(all(((v>>bits)&1)==(bits!=0) for v in truths) for bits in range(16)),{'assignments':16,'reference':'OR of four unchanged input bits','added_registers':0})
 if a.reference_project:
  ref=json.loads((a.reference_project/'candidate-plan.json').read_text());common=[k for k in ref['source_files'] if k.endswith(('.fdc','.rcf'))];ip=[k for k in ref['source_files'] if k.startswith('platform/video_base/ipcore/ddr3_test/')]
  check('previous_timing_and_route_constraints_unchanged',all(plan['source_files'].get(k)==ref['source_files'][k] for k in common),common)
  check('all_compiled_vendor_ip_sources_unchanged',all(plan['source_files'].get(k)==ref['source_files'][k] for k in ip),{'file_count':len(ip)})
  added=set(k for k in plan['source_files'] if k.endswith(('.fdc','.rcf')))-set(common)
  allowed={'board/ddr-ca-maxfan16.fdc'}
  gray_name='board/gray-pointer-cdc.fdc'
  if gray_name in added:
   # H adds this separately reviewed eight-command FDC. Bind its exact bytes
   # and native path audit; other new constraints continue to fail this check.
   gray=root/'compiled'/gray_name;extra_evidence.append(gray)
   gray_sha='9ddc95985a97c9fbc24c17e30c318a7d1a457e1e01687dc0871c869fb42526a8'
   check('additional_gray_fdc_is_exact_reviewed_file',sha(gray)==gray_sha and plan['source_files'][gray_name]==gray_sha,{'sha256':sha(gray)})
   from verify_gray_constraints import verify
   try:
    gray_result=verify(root.resolve(),'full')
    check('additional_gray_native_bounds_pass',gray_result['status']=='PASS',
          {'status':gray_result['status'],'errors':gray_result.get('errors',[]),'reports':
           {k:{n:v for n,v in r.items() if n not in ('paths','skew_groups')} for k,r in gray_result['reports'].items()},'report_sha256':gray_result['sha256']})
   except Exception as error:
    check('additional_gray_native_bounds_pass',False,str(error))
   allowed.add(gray_name)
  check('added_constraints_are_exact_ca_and_optional_audited_gray',added==allowed,{'added':sorted(added),'allowed':sorted(allowed)})
 report=dict(status='PASS_SYNTHESIS_LOCAL_EQUIVALENCE' if all(c['pass_'] for c in checks) else 'FAIL',project=str(root),source_identity=plan['source_identity'],build_id=plan['build_id'],checks=checks,source_sha256={str(f):sha(f) for f in [plan_path,fdc,pds,ccr,vm,*extra_evidence]},limitations=['Local combinational driver equivalence only; no whole-chip formal proof.','Routed fanout, placement delay and core-to-PHY setup require implementation reports.','No timing exceptions are added by the synthesis attribute; the optional exact Gray bounds receive a separate native audit.'])
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');print(json.dumps({'status':report['status'],'output':str(a.output)},indent=2));raise SystemExit(0 if report['status'].startswith('PASS') else 1)
if __name__=='__main__':main()
