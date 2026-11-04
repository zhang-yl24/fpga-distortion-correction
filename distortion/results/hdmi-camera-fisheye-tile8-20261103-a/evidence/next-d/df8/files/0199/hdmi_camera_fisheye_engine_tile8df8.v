`timescale 1ns/1ps
// Isolated tile8 candidate; selected S3 engine/core/cache remain unchanged.
// One complete frame-locked fisheye or identity transaction; no rotation/gamma. Parent must keep source_base
// immutable and exclusively own output_base through done. Raster tags are
// checked again by the writer. No partial result bank is published on fault.
module hdmi_camera_fisheye_engine_tile8 #(parameter WIDTH=1920,HEIGHT=1080,TIMEOUT_BITS=26)(
    input clk,rst_n,input frame_valid,output frame_ready,input cfg_corrected,
    input [27:0] source_base,output_base,input [31:0] frame_id,
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
    // Both sequencer and writer capture this mode on the same frame handshake.
    wire use_tiles=cfg_corrected;
    reg [1:0] state;reg [31:0] index,raster_tag;reg [12:0] column,row,tile_x,stripe_y;
    reg [27:0] destination;
    wire core_frame_ready,writer_frame_ready,coordinate_ready;
    wire result_valid,result_ready,result_masked;wire [23:0] result_rgb,result_tag;
    wire core_failed,writer_failed,writer_done;wire [7:0] core_fault,writer_fault;
    wire [31:0] writer_crc,writer_id,writer_pixels,writer_beats;
    assign frame_ready=state==IDLE && core_frame_ready && writer_frame_ready && !buffer_valid && !failed;
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
    hdmi_camera_fisheye_core #(.WIDTH(WIDTH),.HEIGHT(HEIGHT),.INDEX_BITS(8),.TIMEOUT_BITS(TIMEOUT_BITS)) core(
        .clk(clk),.rst_n(rst_n),.frame_valid(begin_frame),.frame_ready(core_frame_ready),.frame_base(source_base),
        .cfg_corrected(cfg_corrected),
        .in_valid(coordinate_valid),.in_ready(coordinate_ready),.in_u(u),.in_v(v),.in_tag(raster_tag[23:0]),
        .out_valid(result_valid),.out_ready(result_ready),.out_rgb(result_rgb),.out_tag(result_tag),.out_masked(result_masked),
        .araddr(araddr),.arlen(arlen),.arvalid(arvalid),.arready(arready),
        .rdata(rdata),.rvalid(rvalid),.rlast(rlast),.rid(rid),
        .failed(core_failed),.fault(core_fault),.hits(hits),.misses(misses),.completed_queries(completed_queries));
    // One elastic whole-pixel stage isolates cache interpolation/tag control
    // from the writer's burst enables. No pixel/tag can advance separately.
    reg buffer_valid;
    reg [23:0] buffer_rgb,buffer_tag;
    wire writer_input_ready;
    assign result_ready=!buffer_valid || writer_input_ready;
    always @(posedge clk)begin
        if(!rst_n || failed)begin buffer_valid<=0;buffer_rgb<=0;buffer_tag<=0;end
        else if(result_ready)begin
            buffer_valid<=result_valid;
            if(result_valid)begin
                buffer_rgb<=result_masked ? 24'd0:result_rgb;
                buffer_tag<=result_tag;
            end
        end
    end
    // Gamma is fixed off: writer quantizes the sampled RGB exactly once.
    ddr_adaptive_result_writer_dualstripe #(.WIDTH(WIDTH),.HEIGHT(HEIGHT),.TIMEOUT_BITS(TIMEOUT_BITS)) writer(
        .clk(clk),.rst_n(rst_n),.frame_valid(begin_frame),.frame_ready(writer_frame_ready),
        .frame_base(output_base),.frame_id(frame_id),.frame_tiled(use_tiles),.in_valid(buffer_valid && !failed),.in_ready(writer_input_ready),
        .in_rgb(buffer_rgb),.in_tag(buffer_tag),.awaddr(awaddr),.awlen(awlen),.awvalid(awvalid),.awready(awready),
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
            if(core_failed || writer_failed) begin
                failed<=1;fault<=core_failed ? core_fault:writer_fault;done<=0;state<=FAULT;
            end
        end
    end
endmodule
