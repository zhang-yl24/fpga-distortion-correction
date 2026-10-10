"""Bind host-control regressions to their actual source and oracle bytes."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib,json,shutil
root=Path(__file__).resolve().parents[1];work=root/'build/host_control_sim'
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest().upper()
proof=read(work/'start-proof.json');start=datetime.fromisoformat(proof['started_at']).timestamp()
for rel,digest in proof['source_sha256'].items():
    p=root/rel
    assert sha(p)==digest and p.stat().st_mtime<=start,rel
    out=work/'source-snapshot'/rel;out.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,out)
logs={}
for name,marker in [('simulation.log','PASS host control:'),('concurrent-simulation.log','PASS concurrent host control:')]:
    p=work/name;text=p.read_text();assert marker in text and 'Fatal:' not in text and 'ERROR:' not in text
    assert p.stat().st_mtime>=start
    logs[name]={'sha256':sha(p),'pass_line':next(line for line in text.splitlines() if line.startswith(marker))}
result={'passed':True,'recorded_at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),
        'hardware_verified':False,'source_sha256':proof['source_sha256'],'logs':logs,
        'reference':read(work/'reference.json'),
        'scope':'UART parser and atomic CORDIC/KEY0 controller simulation only; no board RX pin, CDC telemetry acknowledgement, arbitrary-angle full-frame or physical display validation yet.'}
out=root/'results/lab-20261007/host-control-simulation-check.json'
out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('PASS source-bound host UART and concurrent command regressions.')
