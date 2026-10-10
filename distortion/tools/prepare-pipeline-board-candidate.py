"""Stage a guarded board candidate after isolated hit-pipeline tests pass."""
from pathlib import Path
import hashlib
import json
import re
import shutil
root=Path(__file__).resolve().parents[1]
lab=root/'results/lab-20261007'
proof=json.loads((lab/'pipeline-hit-native-check.json').read_text());assert proof['passed']
for rel,digest in proof['source_sha256'].items():
    assert hashlib.sha256((root/rel).read_bytes()).hexdigest()==digest,rel
old,new='corrected_adaptive_seed2','corrected_pipeline_hit'
assert not (root/'build'/new/(new+'.pds')).exists(),'Do not rewrite a prepared active board project'
replacement={'rtl\\experimental\\ddr_adaptive_video.v':'rtl\\experimental\\ddr_pipeline_hit_video.v',
             'rtl\\experimental\\adaptive_tiled_frame_engine.v':'rtl\\experimental\\pipeline_hit_frame_engine.v',
             'rtl\\experimental\\ddr_adaptive_cache.v':'rtl\\experimental\\ddr_pipeline_hit_cache.v'}
top=(root/'board'/(old+'.v')).read_text().replace('module '+old+'(', 'module '+new+'(')
assert top.count('ddr_adaptive_video')==1
top=top.replace('ddr_adaptive_video','ddr_pipeline_hit_video')
(root/'board'/(new+'.v')).write_text(top)
tcl=(root/'board'/('build-'+old+'.tcl')).read_text().replace(old,new)
for a,b in replacement.items():
    a,b=a.replace('\\','/'),b.replace('\\','/')
    assert tcl.count(a)==1
    tcl=tcl.replace(a,b)
serial='add_design {D:/English/FPGA/distortion/rtl/experimental/ddr_pipeline_serial_cache.v}'
tcl=tcl.replace('set_arch -family',serial+'\nset_arch -family')
(root/'board'/('build-'+new+'.tcl')).write_text(tcl)
for suffix in ('.fdc','-pins.json'):shutil.copy2(root/'board'/(old+suffix),root/'board'/(new+suffix))
(root/'board'/('program-'+new+'.tcl')).write_text((root/'board'/('program-'+old+'.tcl')).read_text().replace(old,new))
sources=json.loads((root/'board'/(old+'-sources.json')).read_text())
sources=[replacement.get(p,p).replace(old,new) for p in sources]+['rtl\\experimental\\ddr_pipeline_serial_cache.v']
(root/'board'/(new+'-sources.json')).write_text(json.dumps(sources,indent=2)+'\n')
for name in ('build-pds.ps1','program-heartbeat.ps1','read-telemetry.ps1'):
    path=root/'tools'/name;text=path.read_text(encoding='utf-8-sig')
    text=re.sub(r"(?:@|ValidateSet)\(([^)\n]*'corrected_adaptive_seed2'[^)\n]*)\)",
        lambda m:m[0] if "'"+new+"'" in m[0] else m[0][:-1]+",'"+new+"')",text)
    path.write_text(text,encoding='utf-8-sig')
result={'target':new,'hardware_accessed':False,'build_started':False,
    'placement_seed':2,'pin_map_and_constraints_identical':all((root/'board'/(old+s)).read_bytes()==(root/'board'/(new+s)).read_bytes() for s in ('.fdc','-pins.json')),
    'core_clock_mhz':125,'logical_cache_data_capacity_bytes':40960,
    'source_sha256':{p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in sources},
    'native_six_angle_proof_sha256':hashlib.sha256((lab/'pipeline-hit-native-check.json').read_bytes()).hexdigest(),
    'limits':'Candidate preparation only. Same camera table, clocks, hold-fix policy and pins. Four replicated reads may cost routing/resources; mapping and all final multi-corner constraints must pass before finite physical testing. Keep active adaptive builds unchanged.'}
assert result['pin_map_and_constraints_identical']
(lab/'pipeline-board-candidate.json').write_text(json.dumps(result,indent=2)+'\n')
print('Prepared pipeline-hit board candidate; no build or hardware operation started.')
