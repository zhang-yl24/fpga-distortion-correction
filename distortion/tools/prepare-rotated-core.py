"""Generate isolated rotation/guard composition without mutating baseline RTL."""
from pathlib import Path
import importlib.util
import json
import numpy as np

root = Path(__file__).resolve().parents[1]
rtl = root / 'rtl'
candidate = json.loads((root / 'results/calibration-fpga-candidate-20261006/candidate.json').read_text())
c = candidate['integer_config']
# Bound Q9.22 radius using the exact native integer normalization, with two
# LSBs for squared-radius quantization. It does not extend optical calibration.
yy, xx = np.indices((480,640), dtype=np.int64)
nx = (((xx*256-c[0])*c[6]+32768)>>16)
ny = (((yy*256-c[1])*c[7]+32768)>>16)
r2 = ((nx*nx+(1<<21))>>22) + ((ny*ny+(1<<21))>>22)
bound = int(r2.max())+2
(root / 'board/rotation-domain.vh').write_text(f'// Native calibrated domain, integer rounding margin only.\nlocalparam ROT_MAX_R2_Q22={bound};\n')
s = (rtl / 'brown_inverse_mapper.v').read_text()
s = s.replace('module brown_inverse_mapper #(parameter TAG_W=24)', 'module bounded_brown_inverse_mapper #(parameter TAG_W=24,MAX_RADIUS_Q22=0)')
s = s.replace('input in_valid,output wire in_ready', 'input in_black,input in_valid,output wire in_ready')
s = s.replace("black<={black[28:0],1'b0};", 'black<={black[28:0],in_black};')
old = 'black[9]<=black[8] || overflow32(wide(xx)+wide(yy));'
assert old in s
s = s.replace(old, old[:-1]+' || (MAX_RADIUS_Q22>0 && wide(xx)+wide(yy)>MAX_RADIUS_Q22);')
(rtl / 'bounded_brown_inverse_mapper.v').write_text('// Isolated radius-guarded camera mapper; baseline mapper unchanged.\n'+s)
s = (rtl / 'brown_remap_core.v').read_text()
s = s.replace('module brown_remap_core #(', 'module rotated_remap_core #(')
s = s.replace('TIMEOUT_BITS=26\n', 'TIMEOUT_BITS=26,MAX_RADIUS_Q22=0\n')
s = s.replace('    input in_valid,', '''    input signed [23:0] cfg_rot_cx,cfg_rot_cy,
    input signed [31:0] cfg_rot_cos,cfg_rot_sin,
    input in_valid,''')
start = s.index('    assign frame_ready=')
end = s.index('    ddr_remap_sample #(',start)
s = s[:start]+'''    wire rotation_cfg_ready,rotation_in_ready,rotation_valid,rotation_ready,rotation_black;
    wire signed [23:0] rotated_u,rotated_v;wire [TAG_W-1:0] rotated_tag;
    assign frame_ready=local_rst_n && rotation_cfg_ready && mapper_cfg_ready && sampler_frame_ready && !failed;
    wire accept_frame=frame_valid && frame_ready;
    assign in_ready=local_rst_n && rotation_in_ready && !frame_valid && !failed;
    pixel_inverse_rotation #(.TAG_W(TAG_W)) rotation(.clk(clk),.rst(!local_rst_n),
        .cfg_valid(accept_frame),.cfg_ready(rotation_cfg_ready),
        .cfg_cx(cfg_rot_cx),.cfg_cy(cfg_rot_cy),.cfg_cos(cfg_rot_cos),.cfg_sin(cfg_rot_sin),
        .in_valid(in_valid && !frame_valid && !failed),.in_ready(rotation_in_ready),.in_u(in_u),.in_v(in_v),.in_tag(in_tag),
        .out_valid(rotation_valid),.out_ready(rotation_ready),.out_u(rotated_u),.out_v(rotated_v),.out_black(rotation_black),.out_tag(rotated_tag));
    bounded_brown_inverse_mapper #(.TAG_W(TAG_W),.MAX_RADIUS_Q22(MAX_RADIUS_Q22)) mapper(.clk(clk),.rst(!local_rst_n),
        .cfg_valid(accept_frame),.cfg_ready(mapper_cfg_ready),
        .cfg_out_cx(cfg_out_cx),.cfg_out_cy(cfg_out_cy),.cfg_src_cx(cfg_src_cx),.cfg_src_cy(cfg_src_cy),.cfg_src_fx(cfg_src_fx),.cfg_src_fy(cfg_src_fy),
        .cfg_inv_fx(cfg_inv_fx),.cfg_inv_fy(cfg_inv_fy),.cfg_k1(cfg_k1),.cfg_k2(cfg_k2),.cfg_k3(cfg_k3),.cfg_p1(cfg_p1),.cfg_p2(cfg_p2),
        .in_valid(rotation_valid),.in_black(rotation_black),.in_ready(rotation_ready),.in_u(rotated_u),.in_v(rotated_v),.in_tag(rotated_tag),
        .out_valid(mapped_valid),.out_ready(mapped_ready),.out_x(mapped_x),.out_y(mapped_y),.out_black(mapped_black),.out_tag(mapped_tag));
''' + s[end:]
s = s.replace('.frame_valid(frame_valid && mapper_cfg_ready)', '.frame_valid(accept_frame)')
(rtl / 'rotated_remap_core.v').write_text(s)
s = (rtl / 'remap_frame_engine.v').read_text()
s = s.replace('module remap_frame_engine #(parameter WIDTH=640,HEIGHT=480,TIMEOUT_BITS=26)', 'module rotated_frame_engine #(parameter WIDTH=640,HEIGHT=480,TIMEOUT_BITS=26,MAX_RADIUS_Q22=0)')
s = s.replace('    output [27:0] araddr,', '''    input signed [23:0] cfg_rot_cx,cfg_rot_cy,
    input signed [31:0] cfg_rot_cos,cfg_rot_sin,
    output [27:0] araddr,''')
s = s.replace('brown_remap_core #(.WIDTH(WIDTH),.HEIGHT(HEIGHT),.TIMEOUT_BITS(TIMEOUT_BITS))', 'rotated_remap_core #(.WIDTH(WIDTH),.HEIGHT(HEIGHT),.TIMEOUT_BITS(TIMEOUT_BITS),.MAX_RADIUS_Q22(MAX_RADIUS_Q22))')
s = s.replace('        .in_valid(coordinate_valid)', '''        .cfg_rot_cx(cfg_rot_cx),.cfg_rot_cy(cfg_rot_cy),.cfg_rot_cos(cfg_rot_cos),.cfg_rot_sin(cfg_rot_sin),
        .in_valid(coordinate_valid)''')
(rtl / 'rotated_frame_engine.v').write_text(s)
(root / 'results/rotation-domain-20261006.json').write_text(json.dumps({'max_native_integer_radius_squared_q22': int(r2.max()),
    'guard_radius_squared_q22': bound, 'integer_rounding_margin_lsb': 2,
    'native_valid_pixels': int(np.count_nonzero(r2 <= bound)), 'optical_radius': candidate['valid_normalized_radius_max'],
    'scope': 'Masks rotated normalized rays outside the native calibrated radial fit; two integer radius-squared LSBs cover arithmetic rounding only, not new optical evidence.'}, indent=2)+'\n')
print(f'Generated composed inverse rotation -> bounded camera math -> single DDR bilinear engine; radius bound={bound}.')
