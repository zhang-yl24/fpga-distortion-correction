"""Combine two finite physically checked changes in a fresh board target."""
from pathlib import Path
import hashlib,json,re,shutil
root=Path(__file__).resolve().parents[1];lab=root/'results/lab-20261007'
for name in ('host-angle-13_7-check.json','cadence-zero-check.json','cadence-auto-check.json'):
    assert json.loads((lab/name).read_text())['passed'],name
old,new='corrected_host','corrected_host_cadence'
assert not (root/'build'/new/(new+'.pds')).exists(),'Preserve any existing combined board build'
top=(root/'board'/(old+'.v')).read_text().replace('module '+old+'(', 'module '+new+'(')
assert top.count('ov5640_init #')==1
top=top.replace('ov5640_init #','ov5640_cadence_trial_init #')
(root/'board'/(new+'.v')).write_text(top)
tcl=(root/'board'/('build-'+old+'.tcl')).read_text().replace(old,new)
assert tcl.count('/rtl/ov5640_init.v}')==1
tcl=tcl.replace('/rtl/ov5640_init.v}','/rtl/experimental/ov5640_cadence_trial_init.v}')
(root/'board'/('build-'+new+'.tcl')).write_text(tcl)
for suffix in ('.fdc','-pins.json'):shutil.copy2(root/'board'/(old+suffix),root/'board'/(new+suffix))
(root/'board'/('program-'+new+'.tcl')).write_text((root/'board'/('program-'+old+'.tcl')).read_text().replace(old,new))
sources=[p.replace(old,new).replace('rtl\\ov5640_init.v','rtl\\experimental\\ov5640_cadence_trial_init.v').replace('board\\ov5640_commands.vh','board\\ov5640_cadence_trial_commands.vh') for p in json.loads((root/'board'/(old+'-sources.json')).read_text())]
(root/'board'/(new+'-sources.json')).write_text(json.dumps(sources,indent=2)+'\n')
for name in ('build-pds.ps1','program-heartbeat.ps1','read-telemetry.ps1'):
    p=root/'tools'/name;text=p.read_text(encoding='utf-8-sig')
    text=re.sub(r"(?:@|ValidateSet)\(([^)\n]*'corrected_adaptive_seed2'[^)\n]*)\)",lambda m:m[0] if "'"+new+"'" in m[0] else m[0][:-1]+",'"+new+"')",text)
    p.write_text(text,encoding='utf-8-sig')
result={'target':new,'hardware_accessed':False,'source_sha256':{p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in sources},
    'prerequisite_checks':['host-angle-13_7-check.json','cadence-zero-check.json','cadence-auto-check.json'],
    'limits':'Independent host and camera changes have finite physical checks. This combined target still needs final multi-corner timing, all 130 pins/source/bitstream checks and its own finite physical tests; the independent tests do not establish the combined behavior.'}
(lab/'host-cadence-board-candidate.json').write_text(json.dumps(result,indent=2)+'\n')
print('Prepared isolated combined arbitrary-angle host + camera-cadence candidate; no physical claim.')
