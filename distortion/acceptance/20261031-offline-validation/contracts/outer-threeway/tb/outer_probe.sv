`timescale 1ns/1ps
module outer_probe #(parameter integer KIND=0)(
 input wire ref_clk,pclk,reset_n,ready,vs,hs,de,
 output wire qualified,failed,output wire [7:0] fault,
 output wire polarity,vs_idle,hs_idle,output wire [31:0] good,bad,edges,
 output wire [15:0] width_seen,height_seen,
 output wire p_active,r_active,gfailed,tbad,tmeta,ratebad,
 output wire [7:0] gfault,
 output wire request,ack,settle,apply,
 output wire [104:0] held,ref_bundle,
 output wire prun,rrun,source_capture
);
 wire normalized;
 if(KIND==0)begin:b
  hdmi1080_input_status_cdc #(.WIDTH(8),.HEIGHT(4),.HTOTAL(16),.VTOTAL(8),
   .ACTIVITY_REF_CYCLES(64),.PCLK_WINDOW_MIN(174),.PCLK_WINDOW_MAX(182)) m(
   .ref_clk(ref_clk),.pix_clk(pclk),.rst_n(reset_n&&ready),.pix_vs(vs),.pix_hs(hs),.pix_de(de),
   .normalized_vs(normalized),.qualified(qualified),.failed(failed),.fault(fault),
   .polarity_known_ref(polarity),.vs_inactive_ref(vs_idle),.hs_inactive_ref(hs_idle),
   .good_frames(good),.bad_frames(bad),.pclk_edges_per_window(edges),
   .last_pixels_per_line(width_seen),.last_lines(height_seen));
  assign p_active=m.p_reset[1];assign r_active=m.r_reset[1];
  assign gfailed=m.geometry_failed;assign gfault=m.geometry_fault;assign tbad=m.timing_bad_sync[1];assign tmeta=m.timing_bad_sync[0];assign ratebad=m.rate_failed;
  assign request=m.geometry.snapshot_request;assign ack=m.geometry.snapshot_ack;
  assign settle=m.geometry.settle;assign apply=m.geometry.snapshot_apply;
  assign held=m.geometry.held_snapshot;assign ref_bundle=m.geometry.ref_snapshot;
  assign prun=m.geometry.p_run;assign rrun=m.geometry.r_run;
  assign source_capture=m.geometry.request_sync[1]!=m.geometry.snapshot_ack;
 end else if(KIND==1)begin:g
  hdmi1080_input_status_guard_candidate #(.WIDTH(8),.HEIGHT(4),.HTOTAL(16),.VTOTAL(8),
   .ACTIVITY_REF_CYCLES(64),.PCLK_WINDOW_MIN(174),.PCLK_WINDOW_MAX(182)) m(
   .ref_clk(ref_clk),.pix_clk(pclk),.rst_n(reset_n),.readiness_ref(ready),.pix_vs(vs),.pix_hs(hs),.pix_de(de),
   .normalized_vs(normalized),.qualified(qualified),.failed(failed),.fault(fault),
   .polarity_known_ref(polarity),.vs_inactive_ref(vs_idle),.hs_inactive_ref(hs_idle),
   .good_frames(good),.bad_frames(bad),.pclk_edges_per_window(edges),
   .last_pixels_per_line(width_seen),.last_lines(height_seen));
  assign p_active=m.p_active;assign r_active=m.r_active;
  assign gfailed=m.geometry_failed;assign gfault=m.geometry_fault;assign tbad=m.timing_bad_sync[1];assign tmeta=m.timing_bad_sync[0];assign ratebad=m.rate_failed;
  assign request=m.geometry.snapshot_request;assign ack=m.geometry.snapshot_ack;
  assign settle=m.geometry.settle;assign apply=m.geometry.snapshot_apply;
  assign held=m.geometry.held_snapshot;assign ref_bundle=m.geometry.ref_snapshot;
  assign prun=m.geometry.p_run;assign rrun=m.geometry.r_run;
  assign source_capture=m.geometry.request_sync[1]!=m.geometry.snapshot_ack;
 end else begin:s
  hdmi1080_input_status_permit_candidate #(.WIDTH(8),.HEIGHT(4),.HTOTAL(16),.VTOTAL(8),
   .ACTIVITY_REF_CYCLES(64),.PCLK_WINDOW_MIN(174),.PCLK_WINDOW_MAX(182)) m(
   .ref_clk(ref_clk),.pix_clk(pclk),.rst_n(reset_n),.readiness_ref(ready),.pix_vs(vs),.pix_hs(hs),.pix_de(de),
   .normalized_vs(normalized),.qualified(qualified),.failed(failed),.fault(fault),
   .polarity_known_ref(polarity),.vs_inactive_ref(vs_idle),.hs_inactive_ref(hs_idle),
   .good_frames(good),.bad_frames(bad),.pclk_edges_per_window(edges),
   .last_pixels_per_line(width_seen),.last_lines(height_seen));
  assign p_active=m.p_active;assign r_active=m.r_active;
  assign gfailed=m.geometry_failed;assign gfault=m.geometry_fault;assign tbad=m.timing_bad_sync[1];assign tmeta=m.timing_bad_sync[0];assign ratebad=m.rate_failed;
  assign request=m.geometry.snapshot_request;assign ack=m.geometry.snapshot_ack;
  assign settle=m.geometry.settle;assign apply=m.geometry.snapshot_apply;
  assign held=m.geometry.held_snapshot;assign ref_bundle=m.geometry.ref_snapshot;
  assign prun=m.geometry.p_run;assign rrun=m.geometry.r_run;
  assign source_capture=m.geometry.request_sync[1]!=m.geometry.snapshot_ack;
 end
endmodule
