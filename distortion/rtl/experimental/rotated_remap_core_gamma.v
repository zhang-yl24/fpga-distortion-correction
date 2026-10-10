`timescale 1ns/1ps
// A frame hand-off locks both bank and Brown parameters after prior coordinate
// requests drain. Pixel tags survive DDR/cache and interpolation backpressure.
// Already sampled RGB values may still drain downstream; they no longer read
// the old source bank. Parent frame ownership must also cover output storage.
module rotated_remap_core_gamma #(
    parameter WIDTH=640,HEIGHT=480,TAG_W=24,INDEX_BITS=3,TIMEOUT_BITS=26,MAX_RADIUS_Q22=0
)(
    input clk,rst_n,
    input frame_valid,output wire frame_ready,input [27:0] frame_base,
    input signed [23:0] cfg_out_cx,cfg_out_cy,cfg_src_cx,cfg_src_cy,cfg_src_fx,cfg_src_fy,
    input signed [31:0] cfg_inv_fx,cfg_inv_fy,cfg_k1,cfg_k2,cfg_k3,cfg_p1,cfg_p2,
    input signed [23:0] cfg_rot_cx,cfg_rot_cy,
    input signed [31:0] cfg_rot_cos,cfg_rot_sin,
    input in_valid,output wire in_ready,input signed [23:0] in_u,in_v,input [TAG_W-1:0] in_tag,
    output out_valid,input out_ready,output [23:0] out_rgb,output [TAG_W-1:0] out_tag,output out_masked,
    output [27:0] araddr,output [3:0] arlen,output arvalid,input arready,
    input [255:0] rdata,input rvalid,rlast,input [3:0] rid,
    output failed,output [7:0] fault,output [31:0] hits,misses,completed_queries
);
    // External reset asserts immediately and releases through this clock domain.
    // Limit reset distribution fanout before it drives mapper/DSP enables.
    (* async_reg="true" *) reg [1:0] reset_sync=0;
    always @(posedge clk or negedge rst_n)
        if(!rst_n) reset_sync<=0;else reset_sync<={reset_sync[0],1'b1};
    wire local_rst_n /* synthesis syn_maxfan=32 */ = reset_sync[1];
    wire mapper_cfg_ready,sampler_frame_ready,mapper_in_ready;
    wire mapped_valid,mapped_ready,mapped_black;
    wire signed [23:0] mapped_x,mapped_y;wire [TAG_W-1:0] mapped_tag;
    wire rotation_cfg_ready,rotation_in_ready,rotation_valid,rotation_ready,rotation_black;
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
    // A fully unsupported bilinear footprint is masked; actual black remains
    // a valid statistics sample. Partial border footprints retain sampling.
    localparam signed [23:0] LIMIT_X=WIDTH*256,LIMIT_Y=HEIGHT*256;
    wire geometry_mask=mapped_black || mapped_x<=-24'sd256 || mapped_y<=-24'sd256 ||
        mapped_x>=LIMIT_X || mapped_y>=LIMIT_Y;
    wire [TAG_W:0] sampled_tag;
    assign {out_masked,out_tag}=sampled_tag;
    ddr_remap_sample #(.WIDTH(WIDTH),.HEIGHT(HEIGHT),.TAG_W(TAG_W+1),.INDEX_BITS(INDEX_BITS),.TIMEOUT_BITS(TIMEOUT_BITS)) sampler(
        .clk(clk),.rst_n(local_rst_n),.frame_valid(accept_frame),.frame_ready(sampler_frame_ready),.frame_base(frame_base),
        .in_valid(mapped_valid),.in_ready(mapped_ready),.in_x(mapped_x),.in_y(mapped_y),.in_tag({geometry_mask,mapped_tag}),
        .out_valid(out_valid),.out_ready(out_ready),.out_rgb(out_rgb),.out_tag(sampled_tag),
        .araddr(araddr),.arlen(arlen),.arvalid(arvalid),.arready(arready),.rdata(rdata),.rvalid(rvalid),.rlast(rlast),.rid(rid),
        .failed(failed),.fault(fault),.hits(hits),.misses(misses),.completed_queries(completed_queries));
endmodule
