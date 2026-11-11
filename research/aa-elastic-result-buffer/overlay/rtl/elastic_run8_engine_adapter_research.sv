`timescale 1ns/1ps
// Research integration only. One unchanged Run8 KEY1 engine; no fake completion.
// external_fault must not depend combinationally on this module's failed output.
// Active transactions are never reset or AR/AW gated on a new admission fault.
module elastic_run8_engine_adapter_research #(
 parameter [27:0] BANK_STRIDE=28'd33554432,
 parameter [63:0] RESULT2_BASE=64'd4*BANK_STRIDE,
 parameter CRC_FOLD_BITS=2,STATS_ENABLE=1
)(
 input clk,rst_n,external_fault,
 input source_valid,source_complete_qualified,source_bank,
 input [31:0] source_id,source_param_id,
 input source_correction,source_gamma,input [479:0] source_cfg,
 output source_ready,output [1:0] source_writable,
 output source_released,released_bank,output [31:0] released_id,
 input display_request_valid,input [31:0] display_request_epoch,output display_request_ready,
 output display_grant_valid,input display_grant_ready,
 output [1:0] display_slot,output [27:0] display_base,
 output [31:0] display_id,display_crc,display_param_id,display_epoch,
 output [7:0] display_mode,
 input display_done_valid,display_done_qualified,display_reader_finished,display_reader_idle,
 input display_scan_finished,display_fifo_empty,input [1:0] display_done_slot,
 input [31:0] display_done_id,display_done_crc,display_done_epoch,
 output [27:0] araddr,awaddr,output [3:0] arlen,awlen,
 output arvalid,awvalid,input arready,awready,
 input [255:0] rdata,input rvalid,rlast,input [3:0] rid,
 output [255:0] wdata,output [31:0] wstrb,input wready,wlast,
 output processing,pending,display_active,output [1:0] write_slot,front_slot,pending_count,
 output result_published,output reg [1:0] published_slot,
 output reg [27:0] published_base,output reg [31:0] published_id,published_crc,
 output [31:0] completed_frames,output reg [31:0] last_cycles,
 output reg stats_last_valid,output reg [31:0] stats_last_id,stats_last_param_id,stats_last_mode,
 output [31:0] hits,misses,queries,output failed,output [7:0] fault
);
 wire launch_valid,launch_ready,launch_source;
 wire [1:0] launch_slot; wire [27:0] launch_source_base,launch_result_base;
 wire [31:0] launch_id,launch_param;wire launch_correction,launch_gamma;
 wire [479:0] launch_cfg;
 reg active_source;reg [1:0] active_slot;
 wire engine_done,engine_failed;wire [7:0] engine_fault;
 wire [27:0] completed_source_base,completed_base;
 wire [31:0] engine_id,engine_crc,completed_param,completed_cos,completed_sin;
 wire completed_correction,completed_gamma,completed_compressed;
 wire [1:0] owner_display_mode;wire owner_failed,owner_current_fault,raw_source_released,raw_result_published;wire [7:0] owner_fault;
 wire [31:0] logical_issued,logical_retired,scalar_issued,scalar_retired;
 wire [31:0] unused_gamma_frames;wire engine_ready;
 // Native Run8 supports this fixed calibration ROM and identity rotation only
 // in this first system integration. The full cfg480 is still captured by owner.
 wire unsupported_source=source_valid && (source_cfg[63:32]!=32'h40000000 || source_cfg[31:0]!=0);
 wire stop_new=external_fault || unsupported_source;
 assign launch_ready=engine_ready;
 // The unchanged engine raises done only from its DRAIN branch, after writer
 // CRC/count/identity + merge/tone + core/cache idle checks. frame_ready adds
 // selector readiness and IDLE. These are actual engine outputs, never TB force.
 wire done_qualified=engine_done && engine_ready && !engine_failed;
 wire read_quiescent=engine_ready && !arvalid && !engine_failed;
 assign display_mode={6'b0,owner_display_mode};
 assign pending=pending_count!=0;
 assign write_slot=launch_slot;
 assign failed=owner_current_fault;
 assign source_released=raw_source_released && !owner_current_fault;
 assign result_published=raw_result_published && !owner_current_fault;
 assign fault=engine_failed?engine_fault:unsupported_source?8'hE8:owner_failed?owner_fault:owner_current_fault?8'hE9:8'h00;
 initial begin
  if(BANK_STRIDE!=28'd33554432 || RESULT2_BASE!=64'd4*BANK_STRIDE || CRC_FOLD_BITS!=2)
   $fatal(1,"elastic adapter requires canonical stride, plane4 result2 and CRC_FOLD_BITS=2");
 end
 elastic_result_owner_integrated_research #(.ENABLE_ELASTIC_RESULT(1),.BANK_STRIDE(BANK_STRIDE),
  .FRAME_UNITS(28'd1036800),.RESULT2_BASE(RESULT2_BASE)) owner(
  .clk(clk),.rst_n(rst_n),.external_fault(stop_new),.engine_failed(engine_failed),
  .source_valid(source_valid),.source_complete_qualified(source_complete_qualified),.source_bank(source_bank),
  .source_id(source_id),.source_param_id(source_param_id),.source_correction(source_correction),.source_gamma(source_gamma),.source_cfg(source_cfg),
  .source_ready(source_ready),.source_writable(source_writable),.source_released(raw_source_released),.released_bank(released_bank),.released_id(released_id),
  .engine_launch_valid(launch_valid),.engine_launch_ready(launch_ready),.engine_launch_source_bank(launch_source),.engine_launch_result_slot(launch_slot),
  .engine_launch_source_base(launch_source_base),.engine_launch_result_base(launch_result_base),.engine_launch_id(launch_id),.engine_launch_param_id(launch_param),
  .engine_launch_correction(launch_correction),.engine_launch_gamma(launch_gamma),.engine_launch_cfg(launch_cfg),
  .engine_done(engine_done),.engine_done_qualified(done_qualified),.engine_read_quiescent(read_quiescent),
  .engine_done_source_bank(active_source),.engine_done_result_slot(active_slot),
  .engine_done_source_base(completed_source_base),.engine_done_result_base(completed_base),.engine_done_id(engine_id),.engine_done_crc(engine_crc),
  .engine_done_param_id(completed_param),.engine_done_correction(completed_correction),.engine_done_gamma(completed_gamma),
  .engine_done_compressed(completed_compressed),.engine_done_rot_cos(completed_cos),.engine_done_rot_sin(completed_sin),
  .display_request_valid(display_request_valid),.display_request_epoch(display_request_epoch),.display_request_ready(display_request_ready),
  .display_grant_valid(display_grant_valid),.display_grant_ready(display_grant_ready),.display_slot(display_slot),.display_base(display_base),
  .display_id(display_id),.display_crc(display_crc),.display_param_id(display_param_id),.display_epoch(display_epoch),.display_mode(owner_display_mode),
  .display_rot_cos(),.display_rot_sin(),.display_compressed(),
  .display_done_valid(display_done_valid),.display_done_qualified(display_done_qualified),.display_reader_finished(display_reader_finished),
  .display_reader_idle(display_reader_idle),.display_scan_finished(display_scan_finished),.display_fifo_empty(display_fifo_empty),
  .display_done_slot(display_done_slot),.display_done_id(display_done_id),.display_done_crc(display_done_crc),.display_done_epoch(display_done_epoch),
  .processing(processing),.display_active(display_active),.front_valid(),.front_slot(front_slot),.pending_count(pending_count),.free_result_mask(),
  .result_published(raw_result_published),.completed_frames(completed_frames),.current_fault(owner_current_fault),.failed(owner_failed),.fault(owner_fault));
 pipeline_brown_run8_key1_research #(.ENABLE_BLACK_RUN8(1),.CRC_FOLD_BITS(CRC_FOLD_BITS)) engine(
  .clk(clk),.rst_n(rst_n),.frame_valid(launch_valid),.frame_ready(engine_ready),
  .correction_enable(launch_correction),.gamma_enable(launch_gamma),
  .cfg_rot_cos(launch_cfg[63:32]),.cfg_rot_sin(launch_cfg[31:0]),.param_id(launch_param),
  .source_base(launch_source_base),.output_base(launch_result_base),.frame_id(launch_id),
  .completed_source_base(completed_source_base),.completed_param_id(completed_param),
  .completed_correction_enable(completed_correction),.completed_gamma_enable(completed_gamma),
  .completed_rot_cos(completed_cos),.completed_rot_sin(completed_sin),.completed_compressed(completed_compressed),
  .araddr(araddr),.arlen(arlen),.arvalid(arvalid),.arready(arready),.rdata(rdata),.rvalid(rvalid),.rlast(rlast),.rid(rid),
  .awaddr(awaddr),.awlen(awlen),.awvalid(awvalid),.awready(awready),.wdata(wdata),.wstrb(wstrb),.wready(wready),.wlast(wlast),
  .done(engine_done),.failed(engine_failed),.fault(engine_fault),.completed_base(completed_base),.completed_id(engine_id),.completed_crc(engine_crc),
  .hits(hits),.misses(misses),.completed_queries(queries),.logical_issued(logical_issued),.logical_retired(logical_retired),
  .scalar_issued(scalar_issued),.scalar_retired(scalar_retired),.gamma_frames(unused_gamma_frames));
 reg [31:0] cycles,completion_cycles,completion_param,completion_mode;
 always @(posedge clk)begin
  if(!rst_n)begin
   active_source<=0;active_slot<=0;published_slot<=0;published_base<=0;published_id<=0;published_crc<=0;
   cycles<=0;completion_cycles<=0;completion_param<=0;completion_mode<=0;last_cycles<=0;
   stats_last_valid<=0;stats_last_id<=0;stats_last_param_id<=0;stats_last_mode<=0;
  end else begin
   if(source_valid && source_ready)cycles<=0;else if(processing)cycles<=cycles+1'b1;
   // Never infer this allocation from the earlier source_accept edge.
   if(launch_valid && launch_ready)begin active_source<=launch_source;active_slot<=launch_slot;end
   // Register the full publication payload on the actual engine certificate
   // edge. result_published is the owner's independently qualified pulse.
   if(engine_done)begin
    published_slot<=active_slot;published_base<=completed_base;published_id<=engine_id;published_crc<=engine_crc;
    completion_cycles<=cycles;completion_param<=completed_param;
    completion_mode<={30'b0,completed_gamma,completed_correction};
   end
   if(result_published)begin
    last_cycles<=completion_cycles;
    if(STATS_ENABLE)begin stats_last_valid<=1;stats_last_id<=published_id;stats_last_param_id<=completion_param;stats_last_mode<=completion_mode;end
   end
  end
 end
endmodule
