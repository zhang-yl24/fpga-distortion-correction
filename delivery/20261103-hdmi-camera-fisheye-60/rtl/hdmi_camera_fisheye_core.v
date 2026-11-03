`timescale 1ns/1ps
// Frame-locked current HDMI fisheye/identity coordinates and unchanged rowpipe
// DDR sampling. The parent owns source_base through all outstanding reads.
module hdmi_camera_fisheye_core #(
    parameter WIDTH=1920,HEIGHT=1080,TAG_W=24,INDEX_BITS=7,TIMEOUT_BITS=26,ROW_PADDED_INDEX=0,REGISTERED_RETURN=0
)(
    input clk,rst_n,
    input frame_valid,output wire frame_ready,input [27:0] frame_base,
    input cfg_corrected,
    input in_valid,output wire in_ready,input signed [23:0] in_u,in_v,input [TAG_W-1:0] in_tag,
    output out_valid,input out_ready,output [23:0] out_rgb,output [TAG_W-1:0] out_tag,output out_masked,
    output [27:0] araddr,output [3:0] arlen,output arvalid,input arready,
    input [255:0] rdata,input rvalid,rlast,input [3:0] rid,
    output failed,output [7:0] fault,output [31:0] hits,misses,completed_queries
);
    (* PAP_ASYNC_REG=1, syn_srlstyle="registers" *) reg [1:0] reset_sync=0;
    always @(posedge clk or negedge rst_n)
        if(!rst_n)reset_sync<=0;else reset_sync<={reset_sync[0],1'b1};
    wire local_rst_n /* synthesis syn_maxfan=32 */ = reset_sync[1];
    wire mapper_cfg_ready,sampler_frame_ready,mapper_in_ready;
    wire mapped_valid,mapped_ready,mapped_black;
    wire signed [23:0] mapped_x,mapped_y;wire [TAG_W-1:0] mapped_tag;
    assign frame_ready=local_rst_n && mapper_cfg_ready && sampler_frame_ready && !failed;
    wire accept_frame=frame_valid && frame_ready;
    assign in_ready=local_rst_n && mapper_in_ready && !frame_valid && !failed;
    hdmi_camera_fisheye_mapper #(.TAG_W(TAG_W),.WIDTH(WIDTH),.HEIGHT(HEIGHT)) mapper(
        .clk(clk),.rst(!local_rst_n),.cfg_valid(accept_frame),.cfg_ready(mapper_cfg_ready),.cfg_corrected(cfg_corrected),
        .in_valid(in_valid && !frame_valid && !failed),.in_black(1'b0),.in_ready(mapper_in_ready),
        .in_u(in_u),.in_v(in_v),.in_tag(in_tag),
        .out_valid(mapped_valid),.out_ready(mapped_ready),.out_x(mapped_x),.out_y(mapped_y),.out_black(mapped_black),.out_tag(mapped_tag));
    localparam signed [23:0] LIMIT_X=WIDTH*256,LIMIT_Y=HEIGHT*256;
    wire geometry_mask=mapped_black || mapped_x<=-24'sd256 || mapped_y<=-24'sd256 ||
        mapped_x>=LIMIT_X || mapped_y>=LIMIT_Y;
    wire [TAG_W:0] sampled_tag;
    assign {out_masked,out_tag}=sampled_tag;
    ddr_remap_sample_scatter4 #(.WIDTH(WIDTH),.HEIGHT(HEIGHT),.TAG_W(TAG_W+1),.INDEX_BITS(INDEX_BITS),.TIMEOUT_BITS(TIMEOUT_BITS),.ROW_PADDED_INDEX(ROW_PADDED_INDEX),.REGISTERED_RETURN(REGISTERED_RETURN)) sampler(
        .clk(clk),.rst_n(local_rst_n),.frame_valid(accept_frame),.frame_ready(sampler_frame_ready),.frame_base(frame_base),
        .in_valid(mapped_valid),.in_ready(mapped_ready),.in_x(mapped_x),.in_y(mapped_y),.in_tag({geometry_mask,mapped_tag}),
        .out_valid(out_valid),.out_ready(out_ready),.out_rgb(out_rgb),.out_tag(sampled_tag),
        .araddr(araddr),.arlen(arlen),.arvalid(arvalid),.arready(arready),.rdata(rdata),.rvalid(rvalid),.rlast(rlast),.rid(rid),
        .failed(failed),.fault(fault),.hits(hits),.misses(misses),.completed_queries(completed_queries));
endmodule
