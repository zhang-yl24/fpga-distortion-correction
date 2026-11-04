from pathlib import Path
import hashlib,json,shutil,subprocess,sys
root=Path('D:/f60-work/ca-audit-fixture-h')
source=Path('D:/f60-run/physical-h')
pkg=Path('D:/f60/delivery/20261103-hdmi-camera-fisheye-60')
assert not root.exists()
paths=['candidate-plan.json','compiled/board/ddr-ca-maxfan16.fdc',
       'compiled/board/gray-pointer-cdc.fdc','hdmi_camera_fisheye_top.pds',
       'prj_tasks/syn_1/synthesize/constraint_check.ccr',
       'prj_tasks/syn_1/synthesize/hdmi_camera_fisheye_top_syn.vm']
for corner in ('slow','fast'):
    paths += [f'prj_tasks/pnr_1/report_timing/report_db/exception_report_{corner}_set_max_delay_setup.db',
              f'prj_tasks/pnr_1/report_timing/report_db/report_timing_{corner}_path_max_skew.db']
for name in paths:
    target=root/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source/name,target)
for name in ['hdmi_camera_fisheye_top.pds','prj_tasks/syn_1/synthesize/constraint_check.ccr']:
    path=root/name
    path.write_text(path.read_text().replace(source.as_posix(),root.as_posix()))
original_plan=(root/'candidate-plan.json').read_bytes()
gray=root/'compiled/board/gray-pointer-cdc.fdc';original_gray=gray.read_bytes()
results=[]
def run(name,returncode,check=None):
    output=root/(name+'.json')
    proc=subprocess.run([sys.executable,str(pkg/'tools/audit_ddr_ca_fanout.py'),
                         '--project',str(root),'--reference-project','D:/f60-run/physical-b',
                         '--output',str(output)],capture_output=True,text=True)
    report=json.loads(output.read_text())
    assert proc.returncode==returncode,(name,proc.stdout,proc.stderr)
    if check:assert any(c['name']==check and not c['pass_'] for c in report['checks'])
    results.append(dict(case=name,passed=True,exit_code=proc.returncode,status=report['status'],
                        failed_checks=[c['name'] for c in report['checks'] if not c['pass_']]))
run('reviewed_gray_allowed',0)
plan=json.loads(original_plan);plan['source_files']['board/unreviewed.fdc']='0'*64
(root/'candidate-plan.json').write_text(json.dumps(plan))
run('unknown_fdc_rejected',1,'added_constraints_are_exact_ca_and_optional_audited_gray')
(root/'candidate-plan.json').write_bytes(original_plan)
gray.write_bytes(original_gray+b'\nset_false_path -from [get_clocks input_pixel]\n')
plan=json.loads(original_plan);plan['source_files']['board/gray-pointer-cdc.fdc']=hashlib.sha256(gray.read_bytes()).hexdigest()
(root/'candidate-plan.json').write_text(json.dumps(plan))
run('changed_gray_rejected_even_with_updated_manifest',1,'additional_gray_fdc_is_exact_reviewed_file')
gray.write_bytes(original_gray);(root/'candidate-plan.json').write_bytes(original_plan)
report=dict(passed=True,synthetic_auditor_fixtures=True,not_native_implementation_evidence=True,
            tool_sha256=hashlib.sha256((pkg/'tools/audit_ddr_ca_fanout.py').read_bytes()).hexdigest(),cases=results)
(pkg/'evidence/physical-h/ca-auditor-extension-tests.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
