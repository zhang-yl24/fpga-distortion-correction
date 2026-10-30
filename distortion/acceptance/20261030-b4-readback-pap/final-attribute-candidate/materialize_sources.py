from pathlib import Path
import json,hashlib,sys
R=Path(__file__).resolve().parent
out=Path(sys.argv[1]).resolve()
assert not out.exists(), 'destination must not exist; never overwrite frozen inputs'
m=json.loads((R/'manifest.json').read_text())
checked=[]
for e in m['files']:
 b=(R/e['source']).read_bytes()
 assert len(b)==e['bytes'] and hashlib.sha256(b).hexdigest()==e['sha256'],e['path']
 assert not Path(e['path']).is_absolute() and '..' not in Path(e['path']).parts
 checked.append((e['path'],b))
out.mkdir(parents=True)
for rel,b in checked:
 p=out/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
(out/'sources.f').write_bytes((R/'sources.f').read_bytes())
(out/'manifest.json').write_bytes((R/'manifest.json').read_bytes())
print(json.dumps({'sources_materialized':len(checked),'HDL_executed':False}))
