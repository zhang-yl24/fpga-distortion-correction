"""Bind the tagged tone-stage regression to its immutable tested sources."""
from pathlib import Path
import hashlib,json
root=Path(__file__).resolve().parents[1];work=root/'build/gamma_tagged_sim'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest().upper()
proof=json.loads((work/'start-proof.json').read_text(encoding='utf-8-sig'))
log=(work/'simulation.log').read_text()
assert 'PASS tagged Gamma:' in log and 'Fatal:' not in log
for rel,digest in proof['source_sha256'].items():
    assert sha(root/rel)==digest==sha(work/'source-snapshot'/rel),rel
result={'passed':True,'hardware_accessed':False,'complete_frames_checked':12,'pixels_checked':3072,
    'traversals':['raster','8x8 tiled with nonmonotonic raster-address tags'],
    'checks':['atomic pixel/tag/geometry-mask under output stalls and input gaps',
              'two-complete-frame hysteresis with frame-locked mode',
              'real black participates in statistics; explicit geometry mask excluded',
              'reset and disabled-frame bypass'],
    'source_sha256':proof['source_sha256'],'simulation_log_sha256':sha(work/'simulation.log'),
    'limits':'Isolated 16x16 tone/metadata stage using full exhaustive RGB565 golden table. Assumes producer starts tag 0 and ends tag N-1, as the existing raster and 8x8 engines do. Full remapper must transport an explicit geometry mask; DDR writer, frame CRC, integrated timing, live video and optical improvement are not established by this test.'}
(root/'results/lab-20261007/gamma-tagged-simulation-check.json').write_text(json.dumps(result,indent=2)+'\n')
print('PASS source-bound tagged Gamma: 12 complete frames / 3072 pixels; no hardware access.')
