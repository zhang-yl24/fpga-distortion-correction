`timescale 1ns/1ps
// Addendum only: the original six-case stimulus and oracle remain unchanged.
module tb_static_fix_boundaries;
 wire init_finished,crc_finished;
 probe_case #(.MODE(6)) c_init(init_finished);
 probe_case #(.MODE(7)) c_crc(crc_finished);
 reg [95:0] injected_crc;
 reg init_checked=0,crc_checked=0;
 initial begin
  wait(c_init.phase==3 && c_init.dut.gap==2);
  @(negedge c_init.clk);force c_init.init_done=0;
  @(posedge c_init.clk);#1;
  if(!c_init.failed || c_init.fault!=8'h07 || c_init.phase!=8 || c_init.awvalid || c_init.arvalid || c_init.writes!=1)
   $fatal(1,"init-drop terminal-gap guard launched request");
  repeat(8)@(negedge c_init.clk);
  if(c_init.awvalid || c_init.arvalid || c_init.writes!=1)$fatal(1,"init-drop quarantine not stable");
  release c_init.init_done;init_checked=1;
  $display("STATIC_INIT_EDGE_PASS no_new_request=1 fault=07 completed_writes=1");
 end
 initial begin
  wait(c_crc.grp==2 && c_crc.reads==47 && c_crc.ra && c_crc.ri==15);
  @(negedge c_crc.clk);
  injected_crc=c_crc.dut.crc_a ^ 96'h000000010000000000000000;
  force c_crc.dut.crc_a=injected_crc;
  @(posedge c_crc.clk);#1;
  if(!c_crc.failed || c_crc.fault!=8'h06 || c_crc.crc_error_groups!=1 || c_crc.data_error_beats!=0 || c_crc.protocol_errors!=0 || c_crc.done || c_crc.reads!=47)
   $fatal(1,"independent CRC error was promoted to success");
  release c_crc.dut.crc_a;crc_checked=1;
  $display("STATIC_CRC_EDGE_PASS independent_crc_fault=06 data_errors=0 success_suppressed=1");
 end
 initial begin
  wait(init_checked && crc_checked && init_finished && crc_finished);
  $display("STATIC_FIX_BOUNDARIES_PASS cases=2 original_stimulus_unchanged=1");$finish;
 end
 initial begin #1000000;$fatal(1,"static boundary addendum deadline");end
endmodule
