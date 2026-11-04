`timescale 1ns/1ps
// Source-bound readiness-cone OVERAPPROXIMATION, not full top elaboration.
// Timer terminal predicates may occur at any edge or never; RX completion
// and registered driver error are arbitrary. SOURCE_LEDGER maps every state
// update/guard to current sources. No register table/vendor body is included.
module readiness_cone_projection #(parameter integer MODE=0)(
 input wire ref_clk,cfg_clk,reset_n,power_done,configuration_done,
 input wire rx_finish,fault_event,hold_meta,
 output wire readiness,output wire [14:0] debug_state
);
 reg [1:0] ref_reset=0,rx_done_ref=0;
 reg power_ready=0,configuration_ready=0;
 reg [2:0] cfg_reset_pipe=0,seq_reset_pipe=0;
 reg driver_failed=0,failed_latched=0,rx_done=0;
 wire peripheral_reset_n=reset_n && power_ready;
 wire configuration_reset_n=peripheral_reset_n && configuration_ready;
 wire cfg_rst_n=cfg_reset_pipe[2];
 wire failed=driver_failed | failed_latched;
 wire seq_async_rst_n=configuration_reset_n && !failed;
 wire seq_rst_n=seq_reset_pipe[2] && cfg_rst_n && !failed;
 wire init_over_rx=seq_rst_n && rx_done;
 always @(posedge ref_clk or negedge reset_n)
  if(!reset_n)ref_reset<=0;else ref_reset<={ref_reset[0],1'b1};
 always @(posedge ref_clk or negedge reset_n)
  if(!reset_n)power_ready<=0;
  else if(!ref_reset[1])power_ready<=0;
  else if(power_done)power_ready<=1;
 always @(posedge ref_clk or negedge peripheral_reset_n)
  if(!peripheral_reset_n)configuration_ready<=0;
  else if(configuration_done)configuration_ready<=1;
 always @(posedge cfg_clk or negedge configuration_reset_n)
  if(!configuration_reset_n)cfg_reset_pipe<=0;
  else cfg_reset_pipe<={cfg_reset_pipe[1:0],1'b1};
 always @(posedge cfg_clk or negedge cfg_rst_n)
  if(!cfg_rst_n)driver_failed<=0;
  else if(MODE==1 || MODE==3)driver_failed<=fault_event;
  else if(fault_event)driver_failed<=1;
 always @(posedge cfg_clk or negedge configuration_reset_n)
  if(!configuration_reset_n)failed_latched<=0;
  else if(MODE==2 || MODE==3)failed_latched<=0;
  else if(driver_failed)failed_latched<=1;
 always @(posedge cfg_clk or negedge seq_async_rst_n)
  if(!seq_async_rst_n)seq_reset_pipe<=0;
  else seq_reset_pipe<={seq_reset_pipe[1:0],cfg_rst_n};
 // Semantic RX contract checked locally against ALL init_over writers in
 // current source. Its synchronous reset can retain a stale1 while cfg stops.
 always @(posedge cfg_clk)
  if(!seq_rst_n)rx_done<=0;else if(rx_finish)rx_done<=1;
 always @(posedge ref_clk or negedge reset_n)
  if(!reset_n)rx_done_ref<=0;
  else if(!ref_reset[1])rx_done_ref<=0;
  else rx_done_ref<={rx_done_ref[0],hold_meta?rx_done_ref[0]:init_over_rx};
 assign readiness=peripheral_reset_n && rx_done_ref[1];
 assign debug_state={ref_reset,power_ready,configuration_ready,cfg_reset_pipe,
  driver_failed,failed_latched,seq_reset_pipe,rx_done,rx_done_ref};
endmodule
