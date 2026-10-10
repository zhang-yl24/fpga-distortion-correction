"""Create isolated tone-integrated remapper copies; never rewrite live builds."""
from pathlib import Path
import json,hashlib
root=Path(__file__).resolve().parents[1]
def replace(text,old,new):
    assert text.count(old)==1,old
    return text.replace(old,new)
core=(root/'rtl/rotated_remap_core.v').read_text()
core=replace(core,'module rotated_remap_core #(','module rotated_remap_core_gamma #(')
core=replace(core,'output [TAG_W-1:0] out_tag,','output [TAG_W-1:0] out_tag,output out_masked,')
core=replace(core,'    ddr_remap_sample #(','''    // A fully unsupported bilinear footprint is masked; actual black remains
    // a valid statistics sample. Partial border footprints retain sampling.
    localparam signed [23:0] LIMIT_X=WIDTH*256,LIMIT_Y=HEIGHT*256;
    wire geometry_mask=mapped_black || mapped_x<=-24'sd256 || mapped_y<=-24'sd256 ||
        mapped_x>=LIMIT_X || mapped_y>=LIMIT_Y;
    wire [TAG_W:0] sampled_tag;
    assign {out_masked,out_tag}=sampled_tag;
    ddr_remap_sample #(''')
core=replace(core,'.HEIGHT(HEIGHT),.TAG_W(TAG_W),.INDEX_BITS(INDEX_BITS)', '.HEIGHT(HEIGHT),.TAG_W(TAG_W+1),.INDEX_BITS(INDEX_BITS)')
core=replace(core,'.in_y(mapped_y),.in_tag(mapped_tag)', '.in_y(mapped_y),.in_tag({geometry_mask,mapped_tag})')
core=replace(core,'.out_rgb(out_rgb),.out_tag(out_tag)', '.out_rgb(out_rgb),.out_tag(sampled_tag)')
(root/'rtl/experimental/rotated_remap_core_gamma.v').write_text(core)
engine=(root/'rtl/experimental/adaptive_tiled_frame_engine.v').read_text()
engine=replace(engine,'module adaptive_tiled_frame_engine #(', 'module adaptive_gamma_frame_engine #(')
engine=replace(engine,'input clk,rst_n,input frame_valid,output frame_ready,', 'input clk,rst_n,input frame_valid,output frame_ready,input gamma_enable,\n    output [1:0] gamma_mode,output [31:0] gamma_frames,')
engine=replace(engine,'    rotated_remap_core #(', '    rotated_remap_core_gamma #(')
engine=replace(engine,'wire result_valid,result_ready;wire [23:0] result_rgb,result_tag;', 'wire result_valid,result_ready,result_masked;wire [23:0] result_rgb,result_tag;')
engine=replace(engine,'.out_rgb(result_rgb),.out_tag(result_tag),','.out_rgb(result_rgb),.out_tag(result_tag),.out_masked(result_masked),')
engine=replace(engine,'    ddr_adaptive_result_writer #(','''    wire tone_valid,tone_ready,tone_fault,tone_masked;
    wire [15:0] tone_pixel;
    wire [23:0] tone_tag;
    wire [1:0] tone_next;
    adaptive_gamma_tagged #(.WIDTH(WIDTH),.HEIGHT(HEIGHT)) tone(
        .clk(clk),.rst_n(rst_n),.in_valid(result_valid && !failed),.in_ready(result_ready),
        .in_pixel({result_rgb[23:19],result_rgb[15:10],result_rgb[7:3]}),
        .in_tag(result_tag),.in_masked(result_masked),.auto_enable(gamma_enable),
        .out_valid(tone_valid),.out_ready(tone_ready),.out_pixel(tone_pixel),
        .out_tag(tone_tag),.out_masked(tone_masked),.out_mode(gamma_mode),
        .next_mode(tone_next),.completed_frames(gamma_frames),.format_error(tone_fault));
    wire [23:0] tone_rgb={tone_pixel[15:11],tone_pixel[15:13],tone_pixel[10:5],tone_pixel[10:9],tone_pixel[4:0],tone_pixel[4:2]};
    ddr_adaptive_result_writer #(''')
engine=replace(engine,'.in_valid(result_valid && !failed),.in_ready(result_ready),\n        .in_rgb(result_rgb),.in_tag(result_tag)', '.in_valid(tone_valid && !failed),.in_ready(tone_ready),\n        .in_rgb(tone_rgb),.in_tag(tone_tag)')
engine=replace(engine,'if(core_failed || writer_failed) begin','if(core_failed || writer_failed || tone_fault) begin')
engine=replace(engine,'fault<=core_failed ? core_fault:writer_fault;',"fault<=tone_fault ? 8'h41:(core_failed ? core_fault:writer_fault);")
(root/'rtl/experimental/adaptive_gamma_frame_engine.v').write_text(engine)
deps=['rtl/rotated_remap_core.v','rtl/experimental/adaptive_tiled_frame_engine.v']
(root/'results/lab-20261007/gamma-frame-candidate.json').write_text(json.dumps({
    'hardware_accessed':False,'generated_modules':['rotated_remap_core_gamma','adaptive_gamma_frame_engine'],
    'baseline_sources_sha256':{p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in deps},
    'scope':'Copies only; tone stage before final DDR writer and CRC. Explicit full-footprint geometry mask preserved through cache/interpolation tag. Requires independent integration regression and routed timing.'},indent=2)+'\n')
print('Prepared isolated Gamma frame engine; active PDS source dependencies unchanged.')
