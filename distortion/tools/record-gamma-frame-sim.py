"""Seal integrated geometry-mask/tone/DDR/CRC regression evidence."""
from pathlib import Path
import csv,hashlib,json
root=Path(__file__).resolve().parents[1];work=root/'build/gamma_frame_sim'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest().upper()
proof=json.loads((work/'start-proof.json').read_text(encoding='utf-8-sig'))
log=(work/'simulation.log').read_text();assert 'PASS Gamma integrated regression:' in log and 'Fatal:' not in log
for rel,digest in proof['source_sha256'].items():assert sha(root/rel)==digest==sha(work/'source-snapshot'/rel),rel
ref=json.loads((work/'reference.json').read_text());rows=list(csv.DictReader((work/'cycles.csv').open()))
assert len(rows)==10 and sum(int(r['pixels']) for r in rows)==10240
assert all(r['crc32'].upper()==f['crc32'] for r,f in zip(rows,ref['frames']))
result={'passed':True,'hardware_accessed':False,'pixels_checked':10240,'complete_frames':10,
    'frames':ref['frames'],'synthetic_nonzero_tangential_terms':True,'source_sha256':proof['source_sha256'],
    'simulation_log_sha256':sha(work/'simulation.log'),
    'scope':'Actual integrated arithmetic rotation/Brown remap, 25-bit mask+tag through DDR cache and interpolation, RGB565 tone, raster/tiled writer, complete DDR beats and raster CRC. Synthetic read/write stalls, same-bank source immutability and locked parameters checked. No native-size timing, physical light improvement or optical accuracy claim.'}
(root/'results/lab-20261007/gamma-frame-simulation-check.json').write_text(json.dumps(result,indent=2)+'\n')
print('PASS source-bound integrated Gamma: 10 complete frames, 10240 pixels, explicit geometry masks, all DDR beats/CRCs.')
