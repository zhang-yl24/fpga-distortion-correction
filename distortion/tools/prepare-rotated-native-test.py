"""Complete real-frame rotation, bounded projection and one interpolation oracle."""
from pathlib import Path
import importlib.util
import json
import sys
import zlib
import numpy as np

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from model.rotation import phase_from_degrees, cordic, inverse_rotate
from model.reference import remap_fixed
spec = importlib.util.spec_from_file_location('brown', root/'tools/generate-brown-vectors.py')
brown = importlib.util.module_from_spec(spec);spec.loader.exec_module(brown)
config = json.loads((root/'results/calibration-fpga-candidate-20261006/candidate.json').read_text())['integer_config']
bound = json.loads((root/'results/rotation-domain-20261006.json').read_text())['guard_radius_squared_q22']
pairs = json.loads((root/'results/corrected-pair-check-20261006.json').read_text())['pairs']
work = root/'build/rotated_native_sim';work.mkdir(parents=True, exist_ok=True)
angles = [0,30,-30,90,-90,180]
source, result, crcs, configs, frame_stats = [], [], [], [], []
for i, angle in enumerate(angles):
    c, s = cordic(phase_from_degrees(angle));configs.append((c,s))
    q = np.empty((480,640,2),dtype='<i4');masked=0
    for y in range(480):
        for x in range(640):
            u,v,bad = inverse_rotate(x*256,y*256,319*256+128,239*256+128,c,s)
            nx = brown.round_shift((u-config[0])*config[6],16)
            ny = brown.round_shift((v-config[1])*config[7],16)
            r2 = brown.round_shift(nx*nx,22)+brown.round_shift(ny*ny,22)
            if bad or r2>bound:
                q[y,x]=-(1<<23),-(1<<23);masked+=1
            else:
                sx,sy,bad = brown.project(u,v,config)
                q[y,x]=sx,sy;masked+=bad
    raw = (Path(pairs[i%2]['directory'])/'raw-source.rgb565').read_bytes()
    p = np.frombuffer(raw,dtype='<u2').reshape(480,640)
    r,g,b=(p>>11)&31,(p>>5)&63,p&31
    rgb=np.stack(((r<<3)|(r>>2),(g<<2)|(g>>4),(b<<3)|(b>>2)),axis=-1).astype(np.uint8)
    output=remap_fixed(rgb,q[...,0]/256,q[...,1]/256).astype(np.uint16)
    golden=(((output[...,0]>>3)<<11)|((output[...,1]>>2)<<5)|(output[...,2]>>3)).astype('<u2').tobytes()
    if i==0:
        assert masked==0 and golden==(Path(pairs[0]['directory'])/'fpga-corrected.rgb565').read_bytes()
    for payload,array in ((raw,source),(golden,result)):
        array.extend(int.from_bytes(payload[j:j+32],'little') for j in range(0,len(payload),32))
    crcs.append(zlib.crc32(golden))
    frame_stats.append({'angle_deg':angle,'masked_pixels':masked,'crc32':f'{crcs[-1]:08X}'})
    print(f'Prepared rotated native frame angle={angle}, masked={masked}.',flush=True)
for name,array,digits in (('source.mem',source,64),('result.mem',result,64),('crcs.mem',crcs,8)):
    (work/name).write_text(''.join(f'{n:0{digits}x}\n' for n in array))
(work/'rotations.mem').write_text(''.join(f'{c&0xffffffff:08x}{s&0xffffffff:08x}\n' for c,s in configs))
(work/'reference.json').write_text(json.dumps({'frames':frame_stats,'pixels':len(angles)*307200,'single_interpolation':True,'radius_q22':bound,
    'limits':'Integer composition with actual raw captures; mask outside native calibrated radial domain. Does not verify optical model extrapolation, high-resolution calibration or board frame rate.'},indent=2)+'\n')
text=(root/'tests/tb_native_remap_regression.sv').read_text()
text=text.replace('tb_native_remap_regression','tb_rotated_native_regression')
text=text.replace('    reg signed [23:0] src_cx=', '    `include "D:/English/FPGA/distortion/board/rotation-domain.vh"\n    reg signed [31:0] rot_cos,rot_sin;reg [63:0] rotations[0:5];\n    reg signed [23:0] src_cx=')
text=text.replace('remap_frame_engine #(.WIDTH(640),.HEIGHT(480),.TIMEOUT_BITS(16))','rotated_frame_engine #(.WIDTH(640),.HEIGHT(480),.TIMEOUT_BITS(16),.MAX_RADIUS_Q22(ROT_MAX_R2_Q22))')
text=text.replace('        .araddr(araddr),', "        .cfg_rot_cx(24'sd81792),.cfg_rot_cy(24'sd61312),.cfg_rot_cos(rot_cos),.cfg_rot_sin(rot_sin),\n        .araddr(araddr),",1)
text=text.replace('source[0:38399],golden[0:38399]','source[0:115199],golden[0:115199]').replace('crcs[0:1]','crcs[0:5]')
text=text.replace('$readmemh("crcs.mem",crcs);','$readmemh("crcs.mem",crcs);$readmemh("rotations.mem",rotations);')
text=text.replace('phase<2','phase<6').replace('src_cx=CAL_SRC_CX;k1=CAL_K1;frame_valid=1;', 'src_cx=CAL_SRC_CX;k1=CAL_K1;{rot_cos,rot_sin}=rotations[phase];frame_valid=1;')
text=text.replace('src_cx=0;k1=0;', 'src_cx=0;k1=0;rot_cos=0;rot_sin=0;')
text=text.replace('PASS native regression: 614400 real-camera pixels','PASS rotated native regression: 1843200 real-camera pixels')
text=text.replace('#400000000','#900000000')
(root/'tests/tb_rotated_native_regression.sv').write_text(text)
