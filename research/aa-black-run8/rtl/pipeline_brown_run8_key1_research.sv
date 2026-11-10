`timescale 1ns/1ps
// RESEARCH ONLY. Native rational Brown, accepted KEY1/rotation, Gamma OFF only.
// No board/bank wrapper adoption. Source must already be complete and immutable.
// Independent copy: original scalar core/cache/calibration are unchanged.
module pipeline_brown_run8_key1_research #(
 parameter ENABLE_BLACK_RUN8=0,CRC_FOLD_BITS=2,METADATA_DEPTH=2048
)(
 input clk,rst_n,input frame_valid,output frame_ready,
 input correction_enable,gamma_enable,
 input signed [31:0] cfg_rot_cos,cfg_rot_sin,input [31:0] param_id,
 output reg completed_correction_enable,completed_gamma_enable,completed_compressed,
 output reg signed [31:0] completed_rot_cos,completed_rot_sin,
 output reg [31:0] completed_param_id,output reg [27:0] completed_source_base,
 input [27:0] source_base,output_base,input [31:0] frame_id,
 output [27:0] araddr,output [3:0] arlen,output arvalid,input arready,
 input [255:0] rdata,input rvalid,rlast,input [3:0] rid,
 output [27:0] awaddr,output [3:0] awlen,output awvalid,input awready,
 output [255:0] wdata,output [31:0] wstrb,input wready,wlast,
 output reg done,failed,output reg [7:0] fault,
 output reg [27:0] completed_base,output reg [31:0] completed_id,completed_crc,
 output [31:0] hits,misses,completed_queries,
 output [31:0] logical_issued,logical_retired,scalar_issued,scalar_retired,
 output [31:0] gamma_frames
);
 localparam WIDTH=1920,HEIGHT=1080,TILE8_GROUP_WIDTH=64,MACRO_TILE_HEIGHT=32;
 localparam IDLE=0,SCAN=1,DRAIN=2,FAULT=3,FIRST_MACRO_ROWS=32;
 reg [1:0] state;
 reg [31:0] index,raster_tag,macro_first_tag,macro_stripe_first_tag;
 reg [12:0] column,row,tile_x,stripe_y,macro_x,macro_y,macro_last_tile_y;
 reg [27:0] destination,accepted_source_base;
 reg accepted_correction,accepted_gamma,accepted_compressed;
 reg signed [31:0] accepted_rot_cos,accepted_rot_sin;
 reg [31:0] accepted_param_id;
 // Exact compiled profile/layout are fixed below; param_id is identity only,
 // never permission to use an arbitrary calibration with this ROM.
 wire compression_eligible=(ENABLE_BLACK_RUN8!=0)&&correction_enable&&!gamma_enable&&
  cfg_rot_cos==32'sd1073741824&&cfg_rot_sin==32'sd0;
 reg [31:0] identity,query_start;
 reg merge_complete,tone_complete,writer_complete;
 wire selector_ready,selector_valid,selector_black8,selector_last,selector_done,selector_failed;
 wire [3:0]selector_pixels;wire[20:0]selector_ordinal;wire[7:0]selector_fault;
 wire core_frame_ready,writer_frame_ready,merge_frame_ready,tone_frame_ready,token_ready;
 wire core_in_valid,core_in_ready,core_result_valid,core_result_ready,core_result_masked;
 wire [23:0]core_in_tag,core_result_rgb,core_result_tag;
 wire core_failed,writer_failed,writer_done;wire[7:0]core_fault,writer_fault;
 wire[31:0]writer_crc,writer_id,writer_pixels,writer_beats;
 wire merge_valid,merge_ready,merge_masked,merge_black8,merge_last,merge_done,merge_failed;
 wire[23:0]merge_rgb,merge_tag;wire[7:0]merge_fault;
 wire[31:0]merge_issued_tokens,merge_retired_tokens;
 wire tone_valid,tone_ready,tone_masked,tone_black8,tone_done,tone_fault;
 wire[15:0]tone_pixel;wire[23:0]tone_tag;
 wire[31:0]tone_pixels,tone_tokens;
 assign frame_ready=rst_n&&state==IDLE&&!failed&&selector_ready&&core_frame_ready&&writer_frame_ready&&merge_frame_ready&&tone_frame_ready;
 wire[28:0]source_end={1'b0,source_base}+29'd1036800;
 wire[28:0]output_end={1'b0,output_base}+29'd1036800;
 wire valid_layout=source_base[6:0]==0&&output_base[6:0]==0&&source_end<=29'h10000000&&output_end<=29'h10000000&&
  (source_end<={1'b0,output_base}||output_end<={1'b0,source_base});
 wire begin_frame=frame_valid&&frame_ready&&valid_layout&&!gamma_enable;
 wire[31:0]token_last_tag=raster_tag+(selector_black8?7:0);
 wire signed[23:0]u={3'b0,column,8'b0},v={3'b0,row,8'b0};
 fixed_brown_run8_selector selector(.clk(clk),.rst_n(rst_n),.frame_valid(begin_frame),.frame_ready(selector_ready),.frame_compress(compression_eligible),
  .out_valid(selector_valid),.out_ready(token_ready&&state==SCAN&&!failed),.out_ordinal(selector_ordinal),.out_black8(selector_black8),.out_pixels(selector_pixels),.out_last(selector_last),.done(selector_done),.failed(selector_failed),.fault(selector_fault));
 ordered_run8_merge #(.DEPTH(METADATA_DEPTH)) merge(
  .clk(clk),.rst_n(rst_n),.frame_valid(begin_frame),.frame_ready(merge_frame_ready),
  .token_valid(selector_valid&&state==SCAN&&!failed),.token_ready(token_ready),.token_tag(raster_tag[23:0]),.token_black8(selector_black8),.token_last(selector_last),
  .core_in_valid(core_in_valid),.core_in_ready(core_in_ready),.core_in_tag(core_in_tag),
  .core_out_valid(core_result_valid),.core_out_ready(core_result_ready),.core_out_rgb(core_result_rgb),.core_out_tag(core_result_tag),.core_out_masked(core_result_masked),
  .out_valid(merge_valid),.out_ready(merge_ready),.out_rgb(merge_rgb),.out_tag(merge_tag),.out_masked(merge_masked),.out_black8(merge_black8),.out_last(merge_last),
  .done(merge_done),.failed(merge_failed),.fault(merge_fault),.issued_pixels(logical_issued),.retired_pixels(logical_retired),.scalar_issued(scalar_issued),.scalar_retired(scalar_retired),.issued_tokens(merge_issued_tokens),.retired_tokens(merge_retired_tokens));
 rotated_remap_core_gamma_geometry_bypass_scatter4 #(.WIDTH(1920),.HEIGHT(1080),.RATIONAL_BROWN_PROFILE(1),.CACHE_PROFILE(6),.INDEX_BITS(7),
  .PREFETCH_QUERY_DEPTH(4096),.PREFETCH_LOOKAHEAD(512),.CACHE_ROW_STRIDE(2),.CACHE_HEAD_PREDECODE(1),.READ_REQUEST_LOOKAHEAD(0)) core(
  .clk(clk),.rst_n(rst_n),.frame_valid(begin_frame),.frame_ready(core_frame_ready),.frame_base(source_base),.correction_enable(correction_enable),
  .cfg_out_cx(24'sd0),.cfg_out_cy(24'sd0),.cfg_src_cx(24'sd0),.cfg_src_cy(24'sd0),.cfg_src_fx(24'sd0),.cfg_src_fy(24'sd0),
  .cfg_inv_fx(32'sd0),.cfg_inv_fy(32'sd0),.cfg_k1(32'sd0),.cfg_k2(32'sd0),.cfg_k3(32'sd0),.cfg_p1(32'sd0),.cfg_p2(32'sd0),
  .cfg_rot_cx(24'sd0),.cfg_rot_cy(24'sd0),.cfg_rot_cos(cfg_rot_cos),.cfg_rot_sin(cfg_rot_sin),
  .in_valid(core_in_valid),.in_ready(core_in_ready),.in_u(u),.in_v(v),.in_tag(core_in_tag),
  .out_valid(core_result_valid),.out_ready(core_result_ready),.out_rgb(core_result_rgb),.out_tag(core_result_tag),.out_masked(core_result_masked),
  .araddr(araddr),.arlen(arlen),.arvalid(arvalid),.arready(arready),.rdata(rdata),.rvalid(rvalid),.rlast(rlast),.rid(rid),.failed(core_failed),.fault(core_fault),.hits(hits),.misses(misses),.completed_queries(completed_queries));
 fixed_gammaoff_span_tagged #(.WIDTH(1920),.HEIGHT(1080)) tone(
  .clk(clk),.rst_n(rst_n),.frame_valid(begin_frame),.frame_ready(tone_frame_ready),
  .in_valid(merge_valid&&!failed),.in_ready(merge_ready),.in_pixel({merge_rgb[23:19],merge_rgb[15:10],merge_rgb[7:3]}),.in_tag(merge_tag),.in_masked(merge_masked),.in_black_run8(merge_black8),
  .out_valid(tone_valid),.out_ready(tone_ready),.out_pixel(tone_pixel),.out_tag(tone_tag),.out_masked(tone_masked),.out_black_run8(tone_black8),
  .logical_accepted(tone_pixels),.accepted_tokens(tone_tokens),.completed_frames(gamma_frames),.frame_done(tone_done),.format_error(tone_fault));
 wire[23:0]tone_rgb={tone_pixel[15:11],tone_pixel[15:13],tone_pixel[10:5],tone_pixel[10:9],tone_pixel[4:0],tone_pixel[4:2]};
 ddr_tile8_macro_rowburst_writer_run8 #(.WIDTH(1920),.HEIGHT(1080),.GROUP_WIDTH(64),.MACRO_HEIGHT(32),.CRC_FOLD_BITS(CRC_FOLD_BITS),.ENABLE_BLACK_RUN8(ENABLE_BLACK_RUN8)) writer(
  .clk(clk),.rst_n(rst_n),.frame_valid(begin_frame),.frame_tiled(1'b1),.frame_ready(writer_frame_ready),.frame_base(output_base),.frame_id(frame_id),
  .in_valid(tone_valid&&!failed),.in_ready(tone_ready),.in_rgb(tone_rgb),.in_tag(tone_tag),.in_black_run8(tone_black8),
  .awaddr(awaddr),.awlen(awlen),.awvalid(awvalid),.awready(awready),.wdata(wdata),.wstrb(wstrb),.wready(wready),.wlast(wlast),.done(writer_done),.failed(writer_failed),.fault(writer_fault),
  .accepted_pixels(writer_pixels),.written_beats(writer_beats),.last_checksum(writer_crc),.completed_id(writer_id));
 initial if(ENABLE_BLACK_RUN8!=0&&ENABLE_BLACK_RUN8!=1)$fatal(1,"invalid run8 enable");
 always @(posedge clk)begin
  if(!rst_n)begin
   state<=IDLE;index<=0;column<=0;row<=0;raster_tag<=0;tile_x<=0;stripe_y<=0;
   macro_x<=0;macro_y<=0;macro_last_tile_y<=24;macro_first_tag<=0;macro_stripe_first_tag<=0;
   accepted_source_base<=0;accepted_correction<=0;accepted_gamma<=0;accepted_compressed<=0;
   accepted_rot_cos<=0;accepted_rot_sin<=0;accepted_param_id<=0;
   completed_source_base<=0;completed_correction_enable<=0;completed_gamma_enable<=0;completed_compressed<=0;
   completed_rot_cos<=0;completed_rot_sin<=0;completed_param_id<=0;
   destination<=0;identity<=0;query_start<=0;merge_complete<=0;tone_complete<=0;writer_complete<=0;
   done<=0;failed<=0;fault<=0;completed_base<=0;completed_id<=0;completed_crc<=0;
  end else begin
   done<=0;
   if(merge_done)merge_complete<=1;
   if(tone_done)tone_complete<=1;
   if(writer_done)writer_complete<=1;
   case(state)
    IDLE:if(frame_valid&&frame_ready)begin
     if(!valid_layout)begin failed<=1;fault<=8'h40;state<=FAULT;end
     else if(gamma_enable)begin failed<=1;fault<=8'h42;state<=FAULT;end
     else begin
      // These external inputs are also sampled by selector/core on this SAME
      // begin_frame edge. Feeding these registers would introduce a stale frame.
      accepted_source_base<=source_base;accepted_correction<=correction_enable;accepted_gamma<=gamma_enable;
      accepted_compressed<=compression_eligible;accepted_rot_cos<=cfg_rot_cos;accepted_rot_sin<=cfg_rot_sin;accepted_param_id<=param_id;
      index<=0;column<=0;row<=0;raster_tag<=0;tile_x<=0;stripe_y<=0;
      macro_x<=0;macro_y<=0;macro_last_tile_y<=24;macro_first_tag<=0;macro_stripe_first_tag<=0;
      destination<=output_base;identity<=frame_id;query_start<=completed_queries;merge_complete<=0;tone_complete<=0;writer_complete<=0;state<=SCAN;
     end
    end
                SCAN: if(selector_valid && token_ready) begin
                    index<=index+selector_pixels;
                    if(1'b0) begin
                        raster_tag<=raster_tag+1'b1;
                        if(column==WIDTH-1) begin column<=0;row<=row+1'b1;end else column<=column+1'b1;
                    end else begin
                        if(!selector_black8 && column[2:0]!=7) begin column<=column+1'b1;raster_tag<=raster_tag+1'b1;end
                        else if(row[2:0]!=7) begin column<=tile_x;row<=row+1'b1;raster_tag<=token_last_tag+WIDTH-7;end
                        else if(tile_x!=macro_x+TILE8_GROUP_WIDTH-8) begin
                            tile_x<=tile_x+8;column<=tile_x+8;row<=stripe_y;raster_tag<=token_last_tag-7*WIDTH+1;
                        end else if(stripe_y!=macro_last_tile_y) begin
                            stripe_y<=stripe_y+8;tile_x<=macro_x;column<=macro_x;row<=stripe_y+8;
                            raster_tag<=token_last_tag+WIDTH-TILE8_GROUP_WIDTH+1;
                        end else if(macro_x!=WIDTH-TILE8_GROUP_WIDTH) begin
                            macro_x<=macro_x+TILE8_GROUP_WIDTH;tile_x<=macro_x+TILE8_GROUP_WIDTH;
                            column<=macro_x+TILE8_GROUP_WIDTH;stripe_y<=macro_y;row<=macro_y;
                            macro_first_tag<=macro_first_tag+TILE8_GROUP_WIDTH;
                            raster_tag<=macro_first_tag+TILE8_GROUP_WIDTH;
                        end else begin
                            macro_x<=0;macro_y<=macro_y+MACRO_TILE_HEIGHT;
                            tile_x<=0;column<=0;stripe_y<=macro_y+MACRO_TILE_HEIGHT;row<=row+1'b1;
                            macro_stripe_first_tag<=macro_stripe_first_tag+MACRO_TILE_HEIGHT*WIDTH;
                            macro_first_tag<=macro_stripe_first_tag+MACRO_TILE_HEIGHT*WIDTH;
                            macro_last_tile_y<=macro_y+2*MACRO_TILE_HEIGHT<=HEIGHT ?
                                macro_y+2*MACRO_TILE_HEIGHT-8:HEIGHT-8;
                            raster_tag<=token_last_tag+1'b1;
                        end
                    end
                    if(selector_last) state<=DRAIN;
                end
    DRAIN:if((writer_complete||writer_done)&&core_frame_ready&&writer_frame_ready&&merge_frame_ready&&tone_frame_ready)begin
     if(!merge_complete||!tone_complete||logical_retired!=2073600||tone_pixels!=2073600||writer_pixels!=2073600||writer_beats!=129600||writer_id!=identity||scalar_retired!=scalar_issued||(completed_queries-query_start)!=scalar_issued)begin
      failed<=1;fault<=8'h56;state<=FAULT;
     end else begin
      completed_source_base<=accepted_source_base;completed_correction_enable<=accepted_correction;
      completed_gamma_enable<=accepted_gamma;completed_compressed<=accepted_compressed;
      completed_rot_cos<=accepted_rot_cos;completed_rot_sin<=accepted_rot_sin;completed_param_id<=accepted_param_id;
      completed_base<=destination;completed_id<=writer_id;completed_crc<=writer_crc;done<=1;state<=IDLE;end
    end
    FAULT:state<=FAULT;
   endcase
   if(selector_valid&&token_ready&&state==SCAN&&(selector_ordinal!=index || selector_black8&&column[2:0]!=0))begin failed<=1;fault<=8'h55;state<=FAULT;done<=0;end
   if(core_failed||writer_failed||selector_failed||merge_failed||tone_fault)begin
    failed<=1;fault<=tone_fault?8'h41:merge_failed?merge_fault:selector_failed?selector_fault:core_failed?core_fault:writer_fault;state<=FAULT;done<=0;
   end
  end
 end
endmodule
