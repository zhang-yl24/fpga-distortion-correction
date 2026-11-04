`timescale 1ns/1ps
// Independent native1080/development clone; original signed-off source is unchanged.
// One complete accepted-angle corrected frame transaction. Parent must keep source_base
// immutable and exclusively own output_base through done. Raster tags are
// checked again by the writer. No partial result bank is published on fault.
module pipeline_gamma_frame_engine_1080_geometry_bypass #(parameter WIDTH=1920,HEIGHT=1080,TIMEOUT_BITS=26,MAX_RADIUS_Q22=0,RASTER_DOUBLE_BUFFER=0,CACHE_PROFILE=0
)(
    input clk,rst_n,input frame_valid,output frame_ready,input gamma_enable,correction_enable,
    output [1:0] gamma_mode,output [31:0] gamma_frames,
    input [27:0] source_base,output_base,input [31:0] frame_id,
    input signed [23:0] cfg_out_cx,cfg_out_cy,cfg_src_cx,cfg_src_cy,cfg_src_fx,cfg_src_fy,
    input signed [31:0] cfg_inv_fx,cfg_inv_fy,cfg_k1,cfg_k2,cfg_k3,cfg_p1,cfg_p2,
    input signed [23:0] cfg_rot_cx,cfg_rot_cy,
    input signed [31:0] cfg_rot_cos,cfg_rot_sin,
    output [27:0] araddr,output [3:0] arlen,output arvalid,input arready,
    input [255:0] rdata,input rvalid,rlast,input [3:0] rid,
    output [27:0] awaddr,output [3:0] awlen,output awvalid,input awready,
    output [255:0] wdata,output [31:0] wstrb,input wready,wlast,
    output reg done,failed,output reg [7:0] fault,
    output reg [27:0] completed_base,output reg [31:0] completed_id,completed_crc,
    output [31:0] hits,misses,completed_queries
);
    localparam IDLE=0,SCAN=1,DRAIN=2,FAULT=3;
    reg tiled_mode;
    // cfg_rot_* is the wrapper's accepted source snapshot. Writer and
    // scanner latch the same use_tiles decision at begin_frame.
    // Raw bypass ignores Brown AND rotation, so it always scans raster.
    wire use_tiles=correction_enable && (cfg_rot_sin>32'sd1048576 || cfg_rot_sin< -32'sd1048576);
    reg [1:0] state;reg [31:0] index,raster_tag;reg [12:0] column,row,tile_x,stripe_y;
    reg [27:0] destination;
    wire core_frame_ready,writer_frame_ready,coordinate_ready;
    wire result_valid,result_ready,result_masked;wire [23:0] result_rgb,result_tag;
    wire core_failed,writer_failed,writer_done;wire [7:0] core_fault,writer_fault;
    wire [31:0] writer_crc,writer_id,writer_pixels,writer_beats;
    assign frame_ready=state==IDLE && core_frame_ready && writer_frame_ready && !failed;
    localparam FRAME_UNITS=WIDTH*HEIGHT/2; // DDR address unit is four bytes.
    wire [28:0] source_end={1'b0,source_base}+FRAME_UNITS;
    wire [28:0] output_end={1'b0,output_base}+FRAME_UNITS;
    wire valid_layout=source_base[6:0]==0 && output_base[6:0]==0 &&
        source_end<=29'h10000000 && output_end<=29'h10000000 &&
        (source_end<={1'b0,output_base} || output_end<={1'b0,source_base}) &&
        WIDTH>=8 && HEIGHT>=8 && WIDTH%8==0 && HEIGHT%8==0 && WIDTH<=8192 && HEIGHT<=8192 &&
        WIDTH*HEIGHT>=256 && WIDTH*HEIGHT%256==0 && WIDTH*HEIGHT<=16777216;
    wire begin_frame=frame_valid && frame_ready && valid_layout;
    wire coordinate_valid=state==SCAN && !failed;
    wire signed [23:0] u={3'b0,column,8'b0},v={3'b0,row,8'b0};
    rotated_remap_core_gamma_geometry_bypass_scatter4 #(.CACHE_PROFILE(CACHE_PROFILE),.WIDTH(WIDTH),.HEIGHT(HEIGHT),.INDEX_BITS(7),.TIMEOUT_BITS(TIMEOUT_BITS),.MAX_RADIUS_Q22(MAX_RADIUS_Q22)) core(
        .clk(clk),.rst_n(rst_n),.frame_valid(begin_frame),.frame_ready(core_frame_ready),.frame_base(source_base),.correction_enable(correction_enable),
        .cfg_out_cx(cfg_out_cx),.cfg_out_cy(cfg_out_cy),.cfg_src_cx(cfg_src_cx),.cfg_src_cy(cfg_src_cy),
        .cfg_src_fx(cfg_src_fx),.cfg_src_fy(cfg_src_fy),.cfg_inv_fx(cfg_inv_fx),.cfg_inv_fy(cfg_inv_fy),
        .cfg_k1(cfg_k1),.cfg_k2(cfg_k2),.cfg_k3(cfg_k3),.cfg_p1(cfg_p1),.cfg_p2(cfg_p2),
        .cfg_rot_cx(cfg_rot_cx),.cfg_rot_cy(cfg_rot_cy),.cfg_rot_cos(cfg_rot_cos),.cfg_rot_sin(cfg_rot_sin),
        .in_valid(coordinate_valid),.in_ready(coordinate_ready),.in_u(u),.in_v(v),.in_tag(raster_tag[23:0]),
        .out_valid(result_valid),.out_ready(result_ready),.out_rgb(result_rgb),.out_tag(result_tag),.out_masked(result_masked),
        .araddr(araddr),.arlen(arlen),.arvalid(arvalid),.arready(arready),
        .rdata(rdata),.rvalid(rvalid),.rlast(rlast),.rid(rid),
        .failed(core_failed),.fault(core_fault),.hits(hits),.misses(misses),.completed_queries(completed_queries));
    wire tone_valid,tone_ready,tone_fault,tone_masked;
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
    ddr_adaptive_result_writer_capture_local #(.WIDTH(WIDTH),.HEIGHT(HEIGHT),.TIMEOUT_BITS(TIMEOUT_BITS),.RASTER_DOUBLE_BUFFER(RASTER_DOUBLE_BUFFER)) writer(
        .clk(clk),.rst_n(rst_n),.frame_valid(begin_frame),.frame_ready(writer_frame_ready),
        .frame_base(output_base),.frame_id(frame_id),.frame_tiled(use_tiles),.in_valid(tone_valid && !failed),.in_ready(tone_ready),
        .in_rgb(tone_rgb),.in_tag(tone_tag),.awaddr(awaddr),.awlen(awlen),.awvalid(awvalid),.awready(awready),
        .wdata(wdata),.wstrb(wstrb),.wready(wready),.wlast(wlast),.done(writer_done),.failed(writer_failed),.fault(writer_fault),
        .accepted_pixels(writer_pixels),.written_beats(writer_beats),.last_checksum(writer_crc),.completed_id(writer_id));
    always @(posedge clk) begin
        if(!rst_n) begin
            state<=IDLE;tiled_mode<=0;index<=0;column<=0;row<=0;raster_tag<=0;tile_x<=0;stripe_y<=0;destination<=0;done<=0;failed<=0;fault<=0;
            completed_base<=0;completed_id<=0;completed_crc<=0;
        end else begin
            done<=0;
            case(state)
                IDLE: if(frame_valid && frame_ready) begin
                    if(!valid_layout) begin failed<=1;fault<=8'h40;state<=FAULT;end
                    else begin tiled_mode<=use_tiles;index<=0;column<=0;row<=0;raster_tag<=0;tile_x<=0;stripe_y<=0;destination<=output_base;state<=SCAN;end
                end
                SCAN: if(coordinate_ready) begin
                    index<=index+1'b1;
                    if(!tiled_mode) begin
                        raster_tag<=raster_tag+1'b1;
                        if(column==WIDTH-1) begin column<=0;row<=row+1'b1;end else column<=column+1'b1;
                    end else if(column[2:0]!=7) begin column<=column+1'b1;raster_tag<=raster_tag+1'b1;end
                    else if(row[2:0]!=7) begin column<=tile_x;row<=row+1'b1;raster_tag<=raster_tag+WIDTH-7;end
                    else if(tile_x!=WIDTH-8) begin
                        tile_x<=tile_x+8;column<=tile_x+8;row<=stripe_y;raster_tag<=raster_tag-7*WIDTH+1;
                    end else begin tile_x<=0;column<=0;stripe_y<=stripe_y+8;row<=row+1'b1;raster_tag<=raster_tag+1'b1;end
                    if(index==WIDTH*HEIGHT-1) state<=DRAIN;
                end
                DRAIN: if(writer_done) begin
                    completed_base<=destination;completed_id<=writer_id;completed_crc<=writer_crc;
                    done<=1;state<=IDLE;
                end
                FAULT: state<=FAULT;
            endcase
            if(core_failed || writer_failed || tone_fault) begin
                failed<=1;fault<=tone_fault ? 8'h41:(core_failed ? core_fault:writer_fault);done<=0;state<=FAULT;
            end
        end
    end
endmodule
