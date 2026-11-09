`timescale 1ns/1ps
// Connect computed Q15.8 coordinates to four-neighbour DDR sampling and RGB888
// interpolation. Coordinate generation and output-frame storage are upstream
// and downstream modules; this sampler does not contain a coordinate LUT.
module ddr_remap_sample_scatter4 #(
    parameter WIDTH=640,HEIGHT=480,TAG_W=24,INDEX_BITS=3,TIMEOUT_BITS=26,CACHE_PROFILE=0,PREFETCH_QUERY_DEPTH=0,PREFETCH_LOOKAHEAD=256,CACHE_ROW_STRIDE=0,CACHE_HEAD_PREDECODE=1,READ_REQUEST_LOOKAHEAD=0,AF_AA_ORDINAL_TAG_PACK=0
)(
    input clk,rst_n,
    input frame_valid,output frame_ready,input [27:0] frame_base,
    input in_valid,output in_ready,input signed [23:0] in_x,in_y,input [TAG_W-1:0] in_tag,
    output out_valid,input out_ready,output [23:0] out_rgb,output [TAG_W-1:0] out_tag,
    output [27:0] araddr,output [3:0] arlen,output arvalid,input arready,
    input [255:0] rdata,input rvalid,rlast,input [3:0] rid,
    output failed,output [7:0] fault,output [31:0] hits,misses,completed_queries
);
    initial if(AF_AA_ORDINAL_TAG_PACK!=0 && CACHE_PROFILE!=6)
        $fatal(1,"AF packing requires dedicated AA runtime cache profile6");
    wire sample_valid,sample_ready;
    wire [23:0] p00,p10,p01,p11;
    wire [TAG_W-1:0] sample_tag;
    wire [7:0] fx,fy;
    generate if(CACHE_PROFILE==2 || CACHE_PROFILE==3 || CACHE_PROFILE==4 || CACHE_PROFILE==5 || CACHE_PROFILE==6)begin: runtime_cache
    d256_runtime_prefetch_cache #(.AF_AA_ORDINAL_TAG_PACK(AF_AA_ORDINAL_TAG_PACK),.QUERY_DEPTH(PREFETCH_QUERY_DEPTH!=0 ? PREFETCH_QUERY_DEPTH:(CACHE_PROFILE==6 ? 512:256)),.LOOKAHEAD(PREFETCH_LOOKAHEAD),.CACHE_ROW_STRIDE(CACHE_ROW_STRIDE),.READ_REQUEST_LOOKAHEAD(READ_REQUEST_LOOKAHEAD),.COMPACT_COORDS(1),.AREA_PROFILE(2),.CANDIDATE_KEY_PIPE(2),.HEAD_PREDECODE(CACHE_HEAD_PREDECODE),.LOCAL_INFLIGHT_MASK(1),.JOB_DONE_EDGE_SELECT(CACHE_PROFILE==5 || CACHE_PROFILE==6),.FILL_SCATTER8(CACHE_PROFILE==4 || CACHE_PROFILE==5 || CACHE_PROFILE==6),.FILL_SCATTER16(CACHE_PROFILE==3 || CACHE_PROFILE==4 || CACHE_PROFILE==5 || CACHE_PROFILE==6),.FILL_STREAM(CACHE_PROFILE==3 || CACHE_PROFILE==4 || CACHE_PROFILE==5 || CACHE_PROFILE==6),.WIDTH(WIDTH),.HEIGHT(HEIGHT),.TAG_W(TAG_W),.INDEX_BITS(INDEX_BITS),.TIMEOUT_BITS(TIMEOUT_BITS)) cache(
        .clk(clk),.rst_n(rst_n),.frame_valid(frame_valid),.frame_ready(frame_ready),.frame_base(frame_base),
        .in_valid(in_valid),.in_ready(in_ready),.in_x(in_x),.in_y(in_y),.in_tag(in_tag),
        .out_valid(sample_valid),.out_ready(sample_ready),.p00(p00),.p10(p10),.p01(p01),.p11(p11),
        .fx(fx),.fy(fy),.out_tag(sample_tag),.araddr(araddr),.arlen(arlen),.arvalid(arvalid),.arready(arready),
        .rdata(rdata),.rvalid(rvalid),.rlast(rlast),.rid(rid),.failed(failed),.fault(fault),
        .hits(hits),.misses(misses),.completed_queries(completed_queries));
    end else begin: serial_cache
    ddr_neighbour_cache_scatter4_tag_prefetch_local #(.SCATTER8(CACHE_PROFILE==1),.WIDTH(WIDTH),.HEIGHT(HEIGHT),.TAG_W(TAG_W),.INDEX_BITS(INDEX_BITS),.TIMEOUT_BITS(TIMEOUT_BITS)) cache(
        .clk(clk),.rst_n(rst_n),.frame_valid(frame_valid),.frame_ready(frame_ready),.frame_base(frame_base),
        .in_valid(in_valid),.in_ready(in_ready),.in_x(in_x),.in_y(in_y),.in_tag(in_tag),
        .out_valid(sample_valid),.out_ready(sample_ready),.p00(p00),.p10(p10),.p01(p01),.p11(p11),
        .fx(fx),.fy(fy),.out_tag(sample_tag),.araddr(araddr),.arlen(arlen),.arvalid(arvalid),.arready(arready),
        .rdata(rdata),.rvalid(rvalid),.rlast(rlast),.rid(rid),.failed(failed),.fault(fault),
        .hits(hits),.misses(misses),.completed_queries(completed_queries));
    end endgenerate
    bilinear_rgb #(.TAG_W(TAG_W)) interpolation(.clk(clk),.rst(!rst_n),.in_valid(sample_valid),.in_ready(sample_ready),
        .p00(p00),.p10(p10),.p01(p01),.p11(p11),.fx(fx),.fy(fy),.black(1'b0),.in_tag(sample_tag),
        .out_valid(out_valid),.out_ready(out_ready),.out_rgb(out_rgb),.out_tag(out_tag));
endmodule
