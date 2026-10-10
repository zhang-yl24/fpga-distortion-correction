"""Seal exhaustive and adaptive Gamma simulations, with no optical/hardware claim."""
from pathlib import Path
from datetime import datetime
import hashlib,json,shutil
root=Path(__file__).resolve().parents[1];work=root/'build/gamma_sim'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest().upper()
proof=json.loads((work/'start-proof.json').read_text(encoding='utf-8-sig'))
start=datetime.fromisoformat(proof['started_at']).timestamp()
for rel,digest in proof['source_sha256'].items():
    p=root/rel;assert sha(p)==digest and p.stat().st_mtime<=start,rel
    dst=work/'source-snapshot'/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dst)
logs={}
for name in ('tb_adaptive_gamma-simulation.log','tb_gamma_exhaustive-simulation.log'):
    p=work/name;log=p.read_text();assert 'PASS ' in log and 'Fatal:' not in log and 'ERROR:' not in log
    assert p.stat().st_mtime>=start
    logs[name]={'sha256':sha(p),'pass_line':next(x for x in log.splitlines() if x.startswith('PASS '))}
result={'passed':True,'hardware_accessed':False,'source_sha256':proof['source_sha256'],'logs':logs,
    'reference':json.loads((work/'reference.json').read_text()),
    'limits':'Isolated adaptive RGB565 stream; full video CRC integration, actual brightness/exposure behavior, routed resource/timing and strong-light/night optical comparison remain pending. Gamma cannot recover clipped detail.'}
(root/'results/lab-20261007/adaptive-gamma-simulation-check.json').write_text(json.dumps(result,indent=2)+'\n')
print('PASS source-bound adaptive/exhaustive Gamma regressions; physical enhancement still pending.')
