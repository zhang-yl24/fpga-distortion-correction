"""Recover a completed PDS map after the wrapper used the wrong DB basename."""
from pathlib import Path
import hashlib
import json
import re
root=Path(__file__).resolve().parents[1];work=root/'build/pipeline_hit_mapping'
log=work/'build.log';text=log.read_text()
assert 'Executing : dev_map -force_to_run successfully.' in text
assert not re.search(r'(?m)^E:',text)
candidate=json.loads((root/'results/lab-20261007/pipeline-board-candidate.json').read_text())
for rel,digest in candidate['source_sha256'].items():
    path=root/rel;assert hashlib.sha256(path.read_bytes()).hexdigest()==digest
    assert path.stat().st_mtime<=log.stat().st_birthtime
dbs=[work/'synthesize/corrected_pipeline_hit_syn.adf',work/'device_map/corrected_pipeline_hit_map.adf']
for path in dbs:assert path.stat().st_mtime>=log.stat().st_birthtime
rows={}
for name,used,available,percent in re.findall(r'\|\s*(\w+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)',text):
    rows[name]={'used':int(used),'available':int(available),'pds_percent':int(percent)}
result={'passed_mapping':True,'hardware_accessed':False,'pds_compile_synthesis_dev_map_success':True,
    'wrapper_finished_cleanly':False,'wrapper_failure':'Validator expected project-name DB files; PDS generated top-module-name DB files. Original failure retained; filenames fixed for future calls.',
    'top':'corrected_pipeline_hit','device':'PG2L100H','package':'FBG676','mapped_resources':rows,
    'source_sha256':candidate['source_sha256'],'build_log_sha256':hashlib.sha256(log.read_bytes()).hexdigest(),
    'db_sha256':{str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in dbs},
    'limits':'Recovered mapping evidence only, with preprepared source hashes and source mtimes preceding PDS log creation. No routing, clock closure, pin placement, bitstream or physical FPS proof.'}
(work/'mapping-recovered-proof.json').write_text(json.dumps(result,indent=2)+'\n')
(root/'results/lab-20261007/pipeline-mapping-check.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'passed_mapping':True,'mapped_resources':rows}))
