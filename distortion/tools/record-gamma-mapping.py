from pathlib import Path
from datetime import datetime
import hashlib,json,re
root=Path(__file__).resolve().parents[1];work=root/'build/gamma_mapping'
proof=json.loads((work/'start-proof.json').read_text(encoding='utf-8-sig'))
start=datetime.fromisoformat(proof['started_at']).timestamp()
for rel,digest in proof['source_sha256'].items():
    assert hashlib.sha256((root/rel).read_bytes()).hexdigest().upper()==digest
    assert (root/rel).stat().st_mtime<=start
log=work/'build.log';text=log.read_text()
assert 'Executing : dev_map -force_to_run successfully.' in text and not re.search(r'(?m)^E:',text)
db=work/'device_map/adaptive_gamma_stream_map.adf';assert db.stat().st_mtime>=start
resources={n:{'used':int(u),'available':int(a),'pds_percent':int(p)} for n,u,a,p in re.findall(r'\|\s*(\w+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)',text)}
result={'passed_mapping':True,'hardware_accessed':False,'source_sha256':proof['source_sha256'],
    'mapped_resources':resources,'build_log_sha256':hashlib.sha256(log.read_bytes()).hexdigest(),
    'db_sha256':hashlib.sha256(db.read_bytes()).hexdigest(),
    'limits':'Standalone 640x480 statistics/tone module with top-level ports. Device mapping only; no routed frequency, integrated CRC/video or physical low-light effect proof.'}
(root/'results/lab-20261007/gamma-mapping-check.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'passed_mapping':True,'resources':resources}))
