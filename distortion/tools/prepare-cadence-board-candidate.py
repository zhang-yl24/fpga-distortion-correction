"""Integrate tested isolated camera table with the physically verified adaptive design."""
from pathlib import Path
import hashlib
import json
import re
import shutil
root=Path(__file__).resolve().parents[1];lab=root/'results/lab-20261007'
test=json.loads((lab/'camera-cadence-simulation-check.json').read_text());assert test['passed']
for rel,digest in test['source_sha256'].items():assert hashlib.sha256((root/rel).read_bytes()).hexdigest()==digest,rel
physical=json.loads((lab/'adaptive_seed2-auto-check.json').read_text());assert physical['passed']
old,new='corrected_adaptive_seed2','corrected_adaptive_cadence'
assert not (root/'build'/new/(new+'.pds')).exists(),'Do not rewrite an existing board build'
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
sources=json.loads((root/'board'/(old+'-sources.json')).read_text())
sources=[p.replace(old,new).replace('rtl\\ov5640_init.v','rtl\\experimental\\ov5640_cadence_trial_init.v').replace('board\\ov5640_commands.vh','board\\ov5640_cadence_trial_commands.vh') for p in sources]
(root/'board'/(new+'-sources.json')).write_text(json.dumps(sources,indent=2)+'\n')
for name in ('build-pds.ps1','program-heartbeat.ps1','read-telemetry.ps1'):
    path=root/'tools'/name;text=path.read_text(encoding='utf-8-sig')
    text=re.sub(r"(?:@|ValidateSet)\(([^)\n]*'corrected_adaptive_seed2'[^)\n]*)\)",
        lambda m:m[0] if "'"+new+"'" in m[0] else m[0][:-1]+",'"+new+"')",text)
    path.write_text(text,encoding='utf-8-sig')
result={'target':new,'hardware_accessed':False,'build_started':False,
    'pin_map_and_constraints_identical':all((root/'board'/(old+s)).read_bytes()==(root/'board'/(new+s)).read_bytes() for s in ('.fdc','-pins.json')),
    'source_sha256':{p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in sources},
    'expected_sensor_fps':22.7880408,'limits':'Camera timing candidate only. Proven adaptive core, same 125MHz clocks and 48MHz PCLK timing budget. Isolated 3035 divider and banding/readback table tested, but actual sensor cadence, PCLK electrical behavior, exposure, optical quality and thermal effects still require finite physical verification. Original working table and board targets untouched.'}
assert result['pin_map_and_constraints_identical']
(lab/'adaptive-cadence-board-candidate.json').write_text(json.dumps(result,indent=2)+'\n')
print('Prepared isolated adaptive camera-cadence candidate; no hardware access.')
