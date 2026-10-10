"""Independent composed coordinate, calibrated-domain and overflow oracle."""
from pathlib import Path
import importlib.util,json,re,sys
import numpy as np
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
from model.rotation import cordic,phase_from_degrees,inverse_rotate
from model.reference import bilinear_u8
spec=importlib.util.spec_from_file_location('brown',root/'tools/generate-brown-vectors.py')
brown=importlib.util.module_from_spec(spec);spec.loader.exec_module(brown)
config=json.loads((root/'results/calibration-fpga-candidate-20261006/candidate.json').read_text())['integer_config']
bound=json.loads((root/'results/rotation-domain-20261006.json').read_text())['guard_radius_squared_q22']
pairs=json.loads((root/'results/corrected-pair-check-20261006.json').read_text())['pairs']
work=root/'build/rotated_query_sim';work.mkdir(parents=True,exist_ok=True)
coords=[(320*256,240*256)]*64
coords += [(x*256+f,y*256+g) for x in (-400,-1,0,15,16,319,639,640,1000) for y in (-400,-1,0,239,479,480,1000) for f,g in ((0,0),(127,255),(255,1))]
coords += [(a,b) for a in (-(1<<23),(1<<23)-1,0) for b in (-(1<<23),(1<<23)-1,0)]
coords += [tuple(map(int,v)) for v in np.random.default_rng(20261006).integers(-400*256,1000*256,(512,2))]
n=len(coords);rows=[];mapped=[];masked=[];rotations=[]
def rgbint(rgb):return (int(rgb[0])<<16)|(int(rgb[1])<<8)|int(rgb[2])
for phase,angle in enumerate((0,61,-30)):
    cos,sin=cordic(phase_from_degrees(angle));rotations.append((cos,sin));black_count=0
    raw=(Path(pairs[phase%2]['directory'])/'raw-source.rgb565').read_bytes()
    p=np.frombuffer(raw,dtype='<u2').reshape(480,640)
    rr,gg,bb=(p>>11)&31,(p>>5)&63,p&31
    image=np.stack(((rr<<3)|(rr>>2),(gg<<2)|(gg>>4),(bb<<3)|(bb>>2)),axis=-1).astype(np.uint8)
    (work/f'frame{phase}.mem').write_text(''.join(f'{int.from_bytes(raw[i:i+32],"little"):064x}\n' for i in range(0,len(raw),32)))
    for u,v in coords:
        ru,rv,bad=inverse_rotate(u,v,81792,61312,cos,sin)
        nx=brown.round_shift((ru-config[0])*config[6],16);ny=brown.round_shift((rv-config[1])*config[7],16)
        r2=brown.round_shift(nx*nx,22)+brown.round_shift(ny*ny,22)
        if bad or r2>bound:sx=sy=-(1<<23);bad=1
        else:sx,sy,bad=brown.project(ru,rv,config)
        black_count+=bool(bad)
        ix,iy=sx>>8,sy>>8;fx,fy=sx&255,sy&255
        neighbours=[image[iy+dy,ix+dx] if 0<=ix+dx<640 and 0<=iy+dy<480 else np.zeros(3,dtype=np.uint8) for dx,dy in ((0,0),(1,0),(0,1),(1,1))]
        rgb=bilinear_u8(*neighbours,fx,fy)
        rows.append(''.join(f'{value:06x}' for value in (u&0xffffff,v&0xffffff,*map(rgbint,neighbours),rgbint(rgb))))
        mapped.append(f'{(bool(bad)<<48)|((sx&0xffffff)<<24)|(sy&0xffffff):013x}')
    assert black_count>0;masked.append(black_count)
(work/'vectors.mem').write_text('\n'.join(rows)+'\n');(work/'mapped.mem').write_text('\n'.join(mapped)+'\n')
(work/'counts.vh').write_text(f'`define REMAP_QUERIES {n}\n`define REMAP_TOTAL {n*3}\n')
(work/'rotations.mem').write_text(''.join(f'{c&0xffffffff:08x}{s&0xffffffff:08x}\n' for c,s in rotations))
(work/'reference.json').write_text(json.dumps({'queries':n*3,'angles_deg':[0,61,-30],'masked_queries':masked,'radius_q22':bound,'source':'actual RGB565 captures','fault_injection':True},indent=2)+'\n')
t=(root/'tests/tb_brown_ddr_remap.sv').read_text().replace('tb_brown_ddr_remap','tb_rotated_ddr_remap').replace('build/brown_remap_sim/counts.vh','build/rotated_query_sim/counts.vh')
t=t.replace('    brown_remap_core #(.TIMEOUT_BITS(10))',f'    reg signed [31:0] rot_cos,rot_sin;reg [63:0] rotations[0:2];\n    rotated_remap_core #(.TIMEOUT_BITS(10),.MAX_RADIUS_Q22({bound}))')
names=('out_cx','out_cy','src_cx','src_cy','src_fx','src_fy','inv_fx','inv_fy','k1','k2','k3','p1','p2')
for name,value,bits in zip(names,config,[24]*6+[32]*7):
    t=re.sub(r'\.cfg_'+name+r'\([^)]*\)',f".cfg_{name}({bits}'sh{value&((1<<bits)-1):0{bits//4}x})",t)
t=t.replace('        .in_valid(in_valid),',"        .cfg_rot_cx(24'sd81792),.cfg_rot_cy(24'sd61312),.cfg_rot_cos(rot_cos),.cfg_rot_sin(rot_sin),\n        .in_valid(in_valid),",1)
t=t.replace('@(negedge clk);frame_valid=1;frame_base=address;','@(negedge clk);{rot_cos,rot_sin}=rotations[phase<3 ? phase:0];frame_valid=1;frame_base=address;')
t=t.replace('checking=0;mode=0;reset_all();select_frame(0);mode=kind;', 'checking=0;mode=0;phase=0;reset_all();select_frame(0);mode=kind;')
t=t.replace('$readmemh("vectors.mem",vectors);','$readmemh("rotations.mem",rotations);$readmemh("vectors.mem",vectors);')
t=t.replace('PASS composed Brown -> DDR neighbours -> bilinear:', 'PASS composed rotation -> bounded Brown -> DDR neighbours -> bilinear:')
(root/'tests/tb_rotated_ddr_remap.sv').write_text(t)
print(f'Prepared {n*3} composed queries, including {sum(masked)} black-domain/overflow cases.')
