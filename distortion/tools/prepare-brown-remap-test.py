from pathlib import Path
import json
import shutil
import subprocess
import sys
import numpy as np
import importlib.util
spec=importlib.util.spec_from_file_location('brown_reference',Path(__file__).with_name('generate-brown-vectors.py'))
brown=importlib.util.module_from_spec(spec)
spec.loader.exec_module(brown)
parameters,project=brown.parameters,brown.project

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
from model.reference import bilinear_u8
subprocess.run([sys.executable,str(root/'tools/generate-remap-vectors.py')],check=True)
work=root/'build/brown_remap_sim';work.mkdir(parents=True,exist_ok=True)
base=root/'build/remap_sim'
for name in ('frame0.mem','frame1.mem','frame2.mem','counts.vh'):
    shutil.copyfile(base/name,work/name)
meta=json.loads((base/'vectors.json').read_text());n=meta['queries_per_frame']
raw=(base/'vectors.mem').read_text().splitlines()[:n]
coords=[]
for line in raw:
    u=int(line[:6],16);v=int(line[6:12],16)
    coords.append((u-(1<<24) if u&(1<<23) else u,v-(1<<24) if v&(1<<23) else v))
c=parameters((-.24,.065,-.007,.003,-.002))
w,h=640,480;yy,xx=np.indices((h,w),dtype=np.uint32)
rows=[];mapped=[]
def rgbint(rgb):return (int(rgb[0])<<16)|(int(rgb[1])<<8)|int(rgb[2])
for seed in (3,11,29):
    packed=(((xx*7+yy*3+seed)&31)<<11)|(((xx*5+yy*11+seed)&63)<<5)|((xx*13+yy*7+seed)&31)
    rr=(packed>>11)&31;gg=(packed>>5)&63;bb=packed&31
    image=np.stack([(rr<<3)|(rr>>2),(gg<<2)|(gg>>4),(bb<<3)|(bb>>2)],axis=-1).astype(np.uint8)
    for u,v in coords:
        sx,sy,bad=project(u,v,c);ix,iy=sx>>8,sy>>8;fx,fy=sx&255,sy&255
        neighbours=[image[iy+dy,ix+dx] if 0<=ix+dx<w and 0<=iy+dy<h else np.zeros(3,dtype=np.uint8) for dx,dy in ((0,0),(1,0),(0,1),(1,1))]
        rgb=bilinear_u8(*neighbours,fx,fy)
        rows.append(''.join(f'{value:06x}' for value in [u&0xffffff,v&0xffffff,*map(rgbint,neighbours),rgbint(rgb)]))
        mapped.append(f'{(bad<<48)|((sx&0xffffff)<<24)|(sy&0xffffff):013x}')
(work/'vectors.mem').write_text('\n'.join(rows)+'\n')
(work/'mapped.mem').write_text('\n'.join(mapped)+'\n')
names=('cfg_out_cx','cfg_out_cy','cfg_src_cx','cfg_src_cy','cfg_src_fx','cfg_src_fy','cfg_inv_fx','cfg_inv_fy','cfg_k1','cfg_k2','cfg_k3','cfg_p1','cfg_p2')
config_ports=','.join(f'.{name}({bits}\'sh{value&((1<<bits)-1):0{bits//4}x})' for name,value,bits in zip(names,c,[24]*6+[32]*7))
ports=''' .clk(clk),.rst_n(rst_n),.frame_valid(frame_valid),.frame_ready(frame_ready),.frame_base(frame_base),
        .in_valid(in_valid),.in_ready(in_ready),.in_u(in_x),.in_v(in_y),.in_tag(in_tag),
        .out_valid(out_valid),.out_ready(out_ready),.out_rgb(out_rgb),.out_tag(out_tag),
        .araddr(araddr),.arlen(arlen),.arvalid(arvalid),.arready(arready),.rdata(rdata),.rvalid(rvalid),.rlast(rlast),.rid(rid),
        .failed(failed),.fault(fault),.hits(hits),.misses(misses),.completed_queries(completed_queries),'''+config_ports
t=(root/'tests/tb_ddr_remap_sample.sv').read_text()
t=t.replace('tb_ddr_remap_sample','tb_brown_ddr_remap').replace('build/remap_sim/counts.vh','build/brown_remap_sim/counts.vh')
t=t.replace('ddr_remap_sample #(.TIMEOUT_BITS(10)) dut(.*);',f'brown_remap_core #(.TIMEOUT_BITS(10)) dut({ports});')
for field in ('sample_valid','sample_ready','p00','p10','p01','p11','sample_tag','cache.state'):
    t=t.replace('dut.'+field,'dut.sampler.'+field)
t=t.replace('reg [167:0] vectors[0:TOTAL-1];','reg [167:0] vectors[0:TOTAL-1];\n    reg [48:0] mapped[0:TOTAL-1];')
t=t.replace('if(checking && out_valid && out_ready) begin','''if(checking && dut.mapped_valid && dut.mapped_ready) begin
                if({dut.mapped_black,dut.mapped_x,dut.mapped_y}!==mapped[dut.mapped_tag])
                    $fatal(1,"Composed mapper coordinate mismatch tag=%0d",dut.mapped_tag);
            end
            if(checking && out_valid && out_ready) begin''')
t=t.replace('$readmemh("vectors.mem",vectors);','$readmemh("vectors.mem",vectors);$readmemh("mapped.mem",mapped);')
t=t.replace('PASS full-size DDR remap:','PASS composed Brown -> DDR neighbours -> bilinear:')
(root/'tests/tb_brown_ddr_remap.sv').write_text(t)
(work/'vectors.json').write_text(json.dumps(dict(meta,model='brown',parameters=c,coefficients_are_synthetic=True,coordinate_math_is_rtl=True),indent=2)+'\n')
print(f'Prepared composed Brown mapper/DDR/cache/interpolation test with {len(rows)} golden pixels.')
