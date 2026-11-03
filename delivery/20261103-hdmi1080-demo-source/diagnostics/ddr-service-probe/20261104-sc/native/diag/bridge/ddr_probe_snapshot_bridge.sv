`timescale 1ns/1ps
module ddr_probe_snapshot_bridge(
 input core_clk,ref_clk,global_reset_n,
 input probe_started,probe_done,probe_failed,probe_init_done,
 input [7:0] probe_fault,input [3:0] probe_phase,input [1:0] probe_active_group,
 input [31:0] probe_writes,probe_reads,data_error_beats,protocol_errors,timeouts,crc_error_groups,
 input [95:0] group_count,ar_wait_min,ar_wait_max,ar_wait_sum,first_min,first_max,first_sum,last_min,last_max,last_sum,actual_crc,expected_crc,
 output reg snapshot_captured_core=0,output snapshot_valid,output [1183:0] snapshot
);
 (* PAP_ASYNC_REG=1,async_reg="true" *) reg [1:0] core_release=0;
 always @(posedge core_clk or negedge global_reset_n)if(!global_reset_n)core_release<=0;else core_release<={core_release[0],1'b1};
 wire[1183:0] packed_data;wire[4:0] writes5=|probe_writes[31:5] ? 5'd31:probe_writes[4:0];
 wire[5:0] reads6=|probe_reads[31:6] ? 6'd63:probe_reads[5:0];
 assign packed_data[1183:1152]={|timeouts,|protocol_errors,(|data_error_beats)||(|crc_error_groups),reads6,writes5,probe_active_group,probe_phase,probe_init_done,probe_failed,probe_done,probe_started,probe_fault};
 genvar g;generate for(g=0;g<3;g=g+1)begin:groups
  assign packed_data[g*384+:384]={expected_crc[g*32+:32],actual_crc[g*32+:32],last_sum[g*32+:32],last_max[g*32+:32],last_min[g*32+:32],first_sum[g*32+:32],first_max[g*32+:32],first_min[g*32+:32],ar_wait_sum[g*32+:32],ar_wait_max[g*32+:32],ar_wait_min[g*32+:32],group_count[g*32+:32]};
 end endgenerate
 reg terminal_seen=0,pending=0;reg[1183:0] held=0;wire ready;
 always @(posedge core_clk or negedge global_reset_n)begin
  if(!global_reset_n)begin terminal_seen<=0;pending<=0;held<=0;snapshot_captured_core<=0;end
  else if(!core_release[1])begin terminal_seen<=0;pending<=0;held<=0;snapshot_captured_core<=0;end
  else begin
   if(probe_done || probe_failed)terminal_seen<=1;
   if(terminal_seen && !snapshot_captured_core)begin held<=packed_data;pending<=1;snapshot_captured_core<=1;end
   if(pending && ready)pending<=0;
  end
 end
 held_bundle_cdc #(.WIDTH(1184)) transfer(.s_clk(core_clk),.d_clk(ref_clk),.rst_n(global_reset_n),.s_valid(pending),.s_ready(ready),.s_data(held),.d_valid(snapshot_valid),.d_ready(1'b1),.d_data(snapshot));
endmodule
