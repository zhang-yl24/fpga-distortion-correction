`timescale 1ns/1ps
module reset_contract_probe #(parameter integer KIND=0)(
 input wire ref_clk,pclk,reset_n,readiness_ref,vs,href,
 output wire local_reset_n,p_release,r_release,p_run,r_run,
 output wire req,ack,ack_seen,settle,apply,authorize,
 output wire [1:0] request_sync,ack_sync,
 output wire [104:0] held,reference_bundle,
 output wire [31:0] source_good,published_good,
 output wire ref_permit,pixel_permit,blocked
);
 wire [31:0] unused_bad,unused_edges;
 wire [15:0] unused_lines,unused_bytes;
 wire unused_failed;
 wire [7:0] unused_fault;
 if(KIND==1)begin: candidate
  observer_epoch_guard_candidate guard(.ref_clk(ref_clk),.pclk(pclk),
   .reset_n(reset_n),.readiness_ref(readiness_ref),.ref_permit(ref_permit),
   .pixel_permit(pixel_permit),.blocked(blocked));
  assign local_reset_n=reset_n;
  dvp_mode_admission_monitor_epoch_candidate #(
   .BYTES_PER_LINE(8),.LINES_PER_FRAME(4),.ACTIVITY_WINDOW_REF_CYCLES(64),
   .SNAPSHOT_INTERVAL_REF_CYCLES(27000),.STARTUP_REF_CYCLES(1000000),
   .MAX_PCLK_IDLE_REF_CYCLES(1000000),.MAX_VSYNC_IDLE_REF_CYCLES(1000000),
   .MAX_HREF_IDLE_REF_CYCLES(1000000),.MAX_FRAME_IDLE_REF_CYCLES(1000000),
   .MAX_SNAPSHOT_IDLE_REF_CYCLES(1000000)) m(
   .ref_clk(ref_clk),.pclk(pclk),.rst_n(local_reset_n),.enable(1'b1),
   .vsync_active(vs),.href_active(href),.ref_epoch_permit(ref_permit),
   .pixel_epoch_permit(pixel_permit),.raw_authorize(authorize),.failed(unused_failed),
   .fault(unused_fault),.good_frames(published_good),.bad_frames(unused_bad),
   .pclk_edges_per_window(unused_edges),.last_frame_lines(unused_lines),
   .last_line_bytes(unused_bytes),.pclk_fresh(),.vsync_fresh(),.href_fresh(),
   .frame_fresh(),.snapshot_fresh());
  assign p_release=m.p_reset[1];assign r_release=m.r_reset[1];
  assign p_run=m.p_run;assign r_run=m.r_run;
  assign req=m.snapshot_request;assign ack=m.snapshot_ack;assign ack_seen=m.ack_seen;
  assign settle=m.settle;assign apply=m.snapshot_apply;assign request_sync=m.request_sync;
  assign ack_sync=m.ack_sync;assign held=m.held_snapshot;assign reference_bundle=m.ref_snapshot;
  assign source_good=m.source_good_frames;
 end else begin: original
  // KIND0 is the real top's registered-ready AND reset contract.
  // KIND2 deliberately omits the top guard: expected rejection control.
  assign local_reset_n=reset_n && (KIND==0 ? readiness_ref:1'b1);
  assign ref_permit=(KIND==0 ? readiness_ref:1'b1);
  assign pixel_permit=ref_permit;assign blocked=0;
  dvp_mode_admission_monitor_cdc #(
   .BYTES_PER_LINE(8),.LINES_PER_FRAME(4),.ACTIVITY_WINDOW_REF_CYCLES(64),
   .SNAPSHOT_INTERVAL_REF_CYCLES(27000),.STARTUP_REF_CYCLES(1000000),
   .MAX_PCLK_IDLE_REF_CYCLES(1000000),.MAX_VSYNC_IDLE_REF_CYCLES(1000000),
   .MAX_HREF_IDLE_REF_CYCLES(1000000),.MAX_FRAME_IDLE_REF_CYCLES(1000000),
   .MAX_SNAPSHOT_IDLE_REF_CYCLES(1000000)) m(
   .ref_clk(ref_clk),.pclk(pclk),.rst_n(local_reset_n),.enable(1'b1),
   .vsync_active(vs),.href_active(href),.raw_authorize(authorize),.failed(unused_failed),
   .fault(unused_fault),.good_frames(published_good),.bad_frames(unused_bad),
   .pclk_edges_per_window(unused_edges),.last_frame_lines(unused_lines),
   .last_line_bytes(unused_bytes),.pclk_fresh(),.vsync_fresh(),.href_fresh(),
   .frame_fresh(),.snapshot_fresh());
  assign p_release=m.p_reset[1];assign r_release=m.r_reset[1];
  assign p_run=m.p_run;assign r_run=m.r_run;
  assign req=m.snapshot_request;assign ack=m.snapshot_ack;assign ack_seen=m.ack_seen;
  assign settle=m.settle;assign apply=m.snapshot_apply;assign request_sync=m.request_sync;
  assign ack_sync=m.ack_sync;assign held=m.held_snapshot;assign reference_bundle=m.ref_snapshot;
  assign source_good=m.source_good_frames;
 end
endmodule
