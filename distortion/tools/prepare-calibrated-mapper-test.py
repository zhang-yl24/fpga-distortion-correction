"""Exercise the unchanged mapper RTL with actual staged lens coefficients."""
from pathlib import Path
import json
import numpy as np

root=Path(__file__).resolve().parents[1]
candidate=root/'results/calibration-fpga-candidate-20261006'
meta=json.loads((candidate/'candidate.json').read_text());assert meta['passed']
w,h=meta['image_size'];c=meta['integer_config'];n=w*h
xy=np.fromfile(candidate/'coordinates-q8.bin',dtype='<i4').reshape(h,w,2)
work=root/'build/calibrated_mapper_sim';work.mkdir(parents=True,exist_ok=True)
rows=[]
for v in range(h):
    for u in range(w):
        sx,sy=map(int,xy[v,u])
        packed=((u*256)<<73)|((v*256)<<49)|((sx&0xffffff)<<24)|(sy&0xffffff)
        rows.append(f'{packed:025x}')
(work/'vectors.mem').write_text('\n'.join(rows)+'\n')
(work/'configs.mem').write_text(''.join(f'{v&((1<<bits)-1):0{bits//4}x}' for v,bits in zip(c,[24]*6+[32]*7))+'\n')
(work/'counts.vh').write_text(f'`define BROWN_N {n}\n`define BROWN_TOTAL {n}\n')
source=(root/'tests/tb_brown_inverse_mapper.sv').read_text()
source=source.replace('tb_brown_inverse_mapper','tb_calibrated_mapper').replace('build/brown_sim/counts.vh','build/calibrated_mapper_sim/counts.vh')
source=source.replace('configs[0:3]','configs[0:0]').replace('phase<4','phase<1')
source=source.replace('PASS Brown inverse mapper: %0d integer Python golden rays, identity/radial/tangential/overflow, signed Q9.22 math, explicit black domain, configuration drain, tagged output backpressure and mid-pipeline reset recovery.',
    'PASS real-calibration mapper: %0d native-frame integer golden coordinates, staged fisheye polynomial coefficients, signed Q9.22/Q15.8 arithmetic, sustained pipeline input, tagged backpressure and reset recovery.')
(root/'tests/tb_calibrated_mapper.sv').write_text(source)
print(f'Prepared {n} real-parameter coordinate vectors; original synthetic regression remains unchanged.')
