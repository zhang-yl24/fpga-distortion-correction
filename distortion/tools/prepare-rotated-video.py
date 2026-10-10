"""Generate isolated video composition and independent integration references."""
from pathlib import Path
import importlib.util
import json
import sys
import zlib
import numpy as np
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
from model.rotation import cordic,phase_from_degrees,inverse_rotate
from model.reference import bilinear_u8
spec=importlib.util.spec_from_file_location('brown',root/'tools/generate-brown-vectors.py')
brown=importlib.util.module_from_spec(spec);spec.loader.exec_module(brown)
t=(root/'rtl/ddr_corrected_video.v').read_text().replace('module ddr_corrected_video','module ddr_rotated_video')
t=t.replace('parameter WIDTH=640,HEIGHT=480,BANK_STRIDE=262144,','parameter WIDTH=640,HEIGHT=480,BANK_STRIDE=262144,MAX_RADIUS_Q22=0,')
t=t.replace('    output reg [31:0] processed_frames,','    input cfg_rotation_valid,input [31:0] cfg_rotation_phase,\n    input signed [23:0] cfg_rot_cx,cfg_rot_cy,input signed [31:0] cfg_rot_cos,cfg_rot_sin,\n    output reg [31:0] result_phase,\n    output reg [31:0] processed_frames,')
t=t.replace('    reg [31:0] process_cycles;','    reg [31:0] process_cycles,accepted_phase;')
t=t.replace('remap_frame_engine #(.WIDTH(WIDTH),.HEIGHT(HEIGHT))','rotated_frame_engine #(.WIDTH(WIDTH),.HEIGHT(HEIGHT),.MAX_RADIUS_Q22(MAX_RADIUS_Q22))')
t=t.replace('        .araddr(sample_araddr),','        .cfg_rot_cx(cfg_rot_cx),.cfg_rot_cy(cfg_rot_cy),.cfg_rot_cos(cfg_rot_cos),.cfg_rot_sin(cfg_rot_sin),\n        .araddr(sample_araddr),',1)
t=t.replace('processed_frames<=0;last_process_cycles<=0;process_cycles<=0;', 'processed_frames<=0;last_process_cycles<=0;process_cycles<=0;result_phase<=0;accepted_phase<=0;')
t=t.replace('engine_ready && !failed)', 'engine_ready && cfg_rotation_valid && !failed)')
t=t.replace('            if(processing) process_cycles<=', '            if(engine_start && engine_ready) accepted_phase<=cfg_rotation_phase;\n            if(processing) process_cycles<=')
t=t.replace('processing<=0;pending<=1;', 'processing<=0;pending<=1;result_phase<=accepted_phase;')
(root/'rtl/ddr_rotated_video.v').write_text(t)
work=root/'build/rotated_video_sim';work.mkdir(parents=True,exist_ok=True)
w,h=32,16;yy,xx=np.indices((h,w),dtype=np.uint32)
source=[];result=[];crcs=[];coefficients=[]
angles=[0,30,-90]
for phase,seed in enumerate((17,99,201)):
    c=[3968,1920,3968+(128 if phase else 0),1920,8192,8192,1<<25,1<<25,-(1<<19) if phase else 0,0,0,0,0]
    cos,sin=cordic(phase_from_degrees(angles[phase]));coefficients.append((cos,sin))
    raw=((((xx*7+yy*3+seed)&31)<<11)|(((xx*5+yy*11+seed)&63)<<5)|((xx*13+yy*7+seed)&31)).astype('<u2')
    rr,gg,bb=(raw>>11)&31,(raw>>5)&63,raw&31
    image=np.stack(((rr<<3)|(rr>>2),(gg<<2)|(gg>>4),(bb<<3)|(bb>>2)),axis=-1).astype(np.uint8)
    corrected=[]
    for y in range(h):
        for x in range(w):
            u,v,bad=inverse_rotate(x*256,y*256,3968,1920,cos,sin)
            sx,sy,bad=brown.project(u,v,c)
            ix,iy=sx>>8,sy>>8;fx,fy=sx&255,sy&255
            neighbours=[image[iy+dy,ix+dx] if 0<=ix+dx<w and 0<=iy+dy<h else np.zeros(3,dtype=np.uint8) for dx,dy in ((0,0),(1,0),(0,1),(1,1))]
            rgb=bilinear_u8(*neighbours,fx,fy)
            corrected.append(((int(rgb[0])>>3)<<11)|((int(rgb[1])>>2)<<5)|(int(rgb[2])>>3))
    src=raw.tobytes();dst=np.array(corrected,dtype='<u2').tobytes()
    assert phase or dst==src
    for payload,array in ((src,source),(dst,result)):
        array.extend(int.from_bytes(payload[j:j+32],'little') for j in range(0,len(payload),32))
    crcs.append(zlib.crc32(dst))
for name,array,digits in (('source.mem',source,64),('result.mem',result,64),('crcs.mem',crcs,8)):
    (work/name).write_text(''.join(f'{n:0{digits}x}\n' for n in array))
(work/'rotations.mem').write_text(''.join(f'{c&0xffffffff:08x}{s&0xffffffff:08x}\n' for c,s in coefficients))
(work/'phases.mem').write_text(''.join(f'{phase_from_degrees(a):08x}\n' for a in angles))
(work/'reference.json').write_text(json.dumps({'angles_deg':angles,'pixels_per_frame':512,'crcs':crcs,'synthetic_camera':True,'three_clock_domains':True},indent=2)+'\n')
t=(root/'tests/tb_ddr_corrected_video.sv').read_text().replace('tb_ddr_corrected_video','tb_ddr_rotated_video')
t=t.replace('    ddr_corrected_video #(', '    reg signed [31:0] rot_cos,rot_sin;reg [63:0] rotations[0:2];reg [31:0] phases[0:2],rot_phase;wire [31:0] result_phase;\n    ddr_rotated_video #(')
t=t.replace('        .awaddr(awaddr),', "        .cfg_rotation_valid(1'b1),.cfg_rotation_phase(rot_phase),.result_phase(result_phase),\n        .cfg_rot_cx(24'sd3968),.cfg_rot_cy(24'sd1920),.cfg_rot_cos(rot_cos),.cfg_rot_sin(rot_sin),\n        .awaddr(awaddr),",1)
t=t.replace('            cfg_src_cx=active_phase', '            {rot_cos,rot_sin}=rotations[active_phase];rot_phase=phases[active_phase];\n            cfg_src_cx=active_phase')
t=t.replace('begin cfg_src_cx=0;cfg_k1=0;end','begin cfg_src_cx=0;cfg_k1=0;rot_cos=0;rot_sin=0;rot_phase=0;end')
t=t.replace('$readmemh("crcs.mem",crcs);', '$readmemh("crcs.mem",crcs);$readmemh("rotations.mem",rotations);$readmemh("phases.mem",phases);')
t=t.replace('            if(dut.engine_done && !failed) begin', '            if(dut.engine_done && !failed) begin\n                if(dut.accepted_phase!==phases[active_phase]) $fatal(1,"Accepted angle telemetry changed during frame");')
t=t.replace('PASS corrected DDR video:', 'PASS rotated DDR video:').replace('identity and nonlinear Python', 'identity, 30 and -90 degree composed Python')
(root/'tests/tb_ddr_rotated_video.sv').write_text(t)
print('Prepared isolated rotated video and three independent changing-source frame oracles.')
