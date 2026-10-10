"""Seal complete Gamma native/tone or three-clock bypass regression evidence."""
from pathlib import Path
import argparse,csv,hashlib,json
root=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('kind',choices=('native','tone','video'));a=p.parse_args()
folder={'native':'gamma_native_sim','tone':'gamma_native_tone_sim','video':'gamma_video_sim'}[a.kind]
work=root/'build'/folder;sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest().upper()
proof=json.loads((work/'start-proof.json').read_text(encoding='utf-8-sig'))
log=(work/'simulation.log').read_text()
signature='PASS Gamma bypass DDR video:' if a.kind=='video' else 'PASS Gamma native regression:'
assert signature in log and 'Fatal:' not in log
for rel,digest in proof['source_sha256'].items():assert sha(root/rel)==digest==sha(work/'source-snapshot'/rel),rel
result={'passed':True,'hardware_accessed':False,'source_sha256':proof['source_sha256'],
    'simulation_log_sha256':sha(work/'simulation.log')}
if a.kind=='video':
    result.update(scope='Three independent camera/core/HDMI clocks; Gamma explicitly bypassed. Every displayed pixel, DDR/CRC publication, four-bank ownership, capture overlap, malformed response quarantine and mid-processing reset recovery. Enabled tone behavior belongs to separate integrated frame tests, not this bypass video test.')
else:
    ref=json.loads((work/'reference.json').read_text());rows=list(csv.DictReader((work/'cycles.csv').open()))
    assert len(rows)==len(ref['frames']) and sum(int(r['pixels']) for r in rows)==ref['pixels']
    assert all(r['crc32'].upper()==f['crc32'] for r,f in zip(rows,ref['frames']))
    if a.kind=='tone':assert [f['tone_mode'] for f in ref['frames']]==[0,0,1] and ref['synthetically_darkened_source']
    result.update(pixels_checked=ref['pixels'],complete_frames=len(rows),frames=ref['frames'],
        scope=ref['scope']+' Actual 640x480 remap/mask/tone/DDR/CRC pipeline, every pixel, explicit mask/tag, frame-locked mode, immutable source, same-bank invalidation, parameter locking and burst stalls checked. No routed timing or physical optical claim.')
(root/'results/lab-20261007'/('gamma-'+a.kind+'-simulation-check.json')).write_text(json.dumps(result,indent=2)+'\n')
print('PASS source-bound Gamma '+a.kind+' integration evidence.')
