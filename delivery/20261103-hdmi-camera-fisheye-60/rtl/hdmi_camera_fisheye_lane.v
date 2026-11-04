`timescale 1ns/1ps
// One spatial lane of a full-resolution C fisheye frame. The mapper/sampler
// retain WIDTH x HEIGHT calibration and source bounds; only output rows are
// partitioned. Input v is global, tags and output storage are lane-local.
module hdmi_camera_fisheye_lane #(
    parameter WIDTH=1920,HEIGHT=1080,Y_START=0,LANE_HEIGHT=544,
    TILE_W=8,TILE_H=8,TIMEOUT_BITS=26,CACHE_INDEX_BITS=7,ROW_PADDED_INDEX=0
)(
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
    localparam IDLE=0,START=1,SCAN=2,DRAIN=3,FAULT=4;
    localparam SOURCE_UNITS=WIDTH*HEIGHT/2,OUTPUT_UNITS=WIDTH*LANE_HEIGHT/2;
    reg [2:0] state;
    reg [31:0] index,raster_tag;
    reg [12:0] column,row,tile_x,stripe_y,tile_column,tile_row;
    reg [27:0] source_hold,destination;
    reg [31:0] id_hold;
    reg cfg_hold,begin_frame;
    wire [12:0] global_row=row+Y_START;
    wire signed [23:0] u={3'b0,column,8'b0},v={3'b0,global_row,8'b0};
    wire core_frame_ready,writer_frame_ready,coordinate_ready;
    wire result_valid,result_ready,result_masked;
    wire [23:0] result_rgb,result_tag;
    wire core_failed,writer_failed,writer_done;
    wire [7:0] core_fault,writer_fault;
    wire [31:0] writer_crc,writer_id,writer_pixels,writer_beats;
    reg [1:0] buffer_count;
    reg buffer_read,buffer_write;
    reg [23:0] buffer_rgb[0:1],buffer_tag[0:1];
    wire writer_input_ready;
    reg [255:0] returned_data;
    reg [3:0] returned_id;
    reg returned_last,returned_valid;
    // Keep shared-arbiter control off the cache RAM write enables. Payload
    // captures unconditionally, so raw RVALID does not drive a 256-bit CE.
    // Valid is the ownership bit; only it needs reset. All four fields retain
    // the same one-cycle offset, including the first/last beat and bubbles.
    always @(posedge clk)begin
        returned_data<=rdata;returned_id<=rid;returned_last<=rlast;
        if(!rst_n)returned_valid<=0;else returned_valid<=rvalid;
    end
    wire [28:0] source_end={1'b0,source_base}+SOURCE_UNITS;
    wire [28:0] output_end={1'b0,output_base}+OUTPUT_UNITS;
    wire valid_layout=source_base[6:0]==0 && output_base[6:0]==0 &&
        source_end<=29'h10000000 && output_end<=29'h10000000 &&
        (source_end<={1'b0,output_base} || output_end<={1'b0,source_base}) &&
        WIDTH>=16 && HEIGHT>=8 && WIDTH<=8192 && HEIGHT<=8192 &&
        TILE_W>=1 && TILE_H>=1 && WIDTH%TILE_W==0 && LANE_HEIGHT%TILE_H==0 &&
        LANE_HEIGHT>=TILE_H && Y_START>=0 && Y_START+LANE_HEIGHT<=HEIGHT &&
        WIDTH*HEIGHT<=16777216 && WIDTH*HEIGHT%256==0 &&
        WIDTH*LANE_HEIGHT>=256 && WIDTH*LANE_HEIGHT%256==0;
    assign frame_ready=state==IDLE && core_frame_ready && writer_frame_ready && buffer_count==0 && !failed;
    // Accept and retain the entire descriptor before the wide initialization
    // pulse. START reserves one edge for core/writer reset; SCAN begins after
    // that edge, so coordinate zero cannot collide with frame initialization.
    wire coordinate_valid=state==SCAN && !failed;
    hdmi_camera_fisheye_core #(.WIDTH(WIDTH),.HEIGHT(HEIGHT),.INDEX_BITS(CACHE_INDEX_BITS),.TIMEOUT_BITS(TIMEOUT_BITS),.ROW_PADDED_INDEX(ROW_PADDED_INDEX),.REGISTERED_RETURN(1)) core(
        .clk(clk),.rst_n(rst_n),.frame_valid(begin_frame),.frame_ready(core_frame_ready),.frame_base(source_hold),
        .cfg_corrected(cfg_hold),.in_valid(coordinate_valid),.in_ready(coordinate_ready),.in_u(u),.in_v(v),.in_tag(raster_tag[23:0]),
        .out_valid(result_valid),.out_ready(result_ready),.out_rgb(result_rgb),.out_tag(result_tag),.out_masked(result_masked),
        .araddr(araddr),.arlen(arlen),.arvalid(arvalid),.arready(arready),
        .rdata(returned_data),.rvalid(returned_valid),.rlast(returned_last),.rid(returned_id),
        .failed(core_failed),.fault(core_fault),.hits(hits),.misses(misses),.completed_queries(completed_queries));

    // Two complete pixels isolate sampler readiness from writer tag/address
    // and stripe ownership logic. No full+pop lookahead: ready depends only
    // on registered occupancy, while occupancy one sustains one pixel/clock.
    assign result_ready=buffer_count<2 && !failed;
    wire buffer_push=result_valid && result_ready;
    wire buffer_pop=buffer_count!=0 && writer_input_ready && !failed;
    always @(posedge clk)begin
        if(!rst_n || failed || begin_frame)begin buffer_count<=0;buffer_read<=0;buffer_write<=0;end
        else begin
            case({buffer_push,buffer_pop})
                2'b10:buffer_count<=buffer_count+1'b1;
                2'b01:buffer_count<=buffer_count-1'b1;
                default:buffer_count<=buffer_count;
            endcase
            if(buffer_push)begin
                buffer_rgb[buffer_write]<=result_masked ? 24'd0:result_rgb;
                buffer_tag[buffer_write]<=result_tag;buffer_write<=!buffer_write;
            end
            if(buffer_pop)buffer_read<=!buffer_read;
        end
    end
    ddr_adaptive_result_writer #(.WIDTH(WIDTH),.HEIGHT(LANE_HEIGHT),.TILE_W(TILE_W),.TILE_H(TILE_H),.TIMEOUT_BITS(TIMEOUT_BITS)) writer(
        .clk(clk),.rst_n(rst_n),.frame_valid(begin_frame),.frame_ready(writer_frame_ready),
        .frame_base(destination),.frame_id(id_hold),.frame_tiled(1'b1),
        .in_valid(buffer_count!=0 && !failed),.in_ready(writer_input_ready),
        .in_rgb(buffer_rgb[buffer_read]),.in_tag(buffer_tag[buffer_read]),
        .awaddr(awaddr),.awlen(awlen),.awvalid(awvalid),.awready(awready),.wdata(wdata),.wstrb(wstrb),.wready(wready),.wlast(wlast),
        .done(writer_done),.failed(writer_failed),.fault(writer_fault),.accepted_pixels(writer_pixels),.written_beats(writer_beats),
        .last_checksum(writer_crc),.completed_id(writer_id));
    always @(posedge clk)begin
        if(!rst_n)begin
            state<=IDLE;index<=0;raster_tag<=0;column<=0;row<=0;tile_x<=0;stripe_y<=0;tile_column<=0;tile_row<=0;
            source_hold<=0;destination<=0;id_hold<=0;cfg_hold<=0;begin_frame<=0;
            done<=0;failed<=0;fault<=0;completed_base<=0;completed_id<=0;completed_crc<=0;
        end else begin
            done<=0;begin_frame<=0;
            case(state)
                IDLE:if(frame_valid && frame_ready)begin
                    if(!valid_layout)begin failed<=1;fault<=8'h40;state<=FAULT;end
                    else begin
                        index<=0;raster_tag<=0;column<=0;row<=0;tile_x<=0;stripe_y<=0;tile_column<=0;tile_row<=0;
                        source_hold<=source_base;destination<=output_base;id_hold<=frame_id;cfg_hold<=cfg_corrected;
                        begin_frame<=1;state<=START;
                    end
                end
                START:state<=SCAN;
                SCAN:if(coordinate_valid && coordinate_ready)begin
                    index<=index+1'b1;
                    if(tile_column!=TILE_W-1)begin column<=column+1'b1;tile_column<=tile_column+1'b1;raster_tag<=raster_tag+1'b1;end
                    else if(tile_row!=TILE_H-1)begin
                        column<=tile_x;row<=row+1'b1;tile_column<=0;tile_row<=tile_row+1'b1;raster_tag<=raster_tag+WIDTH-TILE_W+1;
                    end else if(tile_x!=WIDTH-TILE_W)begin
                        tile_x<=tile_x+TILE_W;column<=tile_x+TILE_W;row<=stripe_y;tile_column<=0;tile_row<=0;
                        raster_tag<=raster_tag-(TILE_H-1)*WIDTH+1;
                    end else begin
                        tile_x<=0;column<=0;stripe_y<=stripe_y+TILE_H;row<=row+1'b1;tile_column<=0;tile_row<=0;raster_tag<=raster_tag+1'b1;
                    end
                    if(index==WIDTH*LANE_HEIGHT-1)state<=DRAIN;
                end
                DRAIN:if(writer_done)begin
                    completed_base<=destination;completed_id<=writer_id;completed_crc<=writer_crc;done<=1;state<=IDLE;
                end
                FAULT:state<=FAULT;
            endcase
            if(core_failed || writer_failed)begin
                failed<=1;fault<=core_failed ? core_fault:writer_fault;done<=0;begin_frame<=0;state<=FAULT;
            end
        end
    end
endmodule
