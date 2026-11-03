`timescale 1ns/1ps
module ddr_probe_readout #(
 parameter integer GAP_CLKS=6750000,MAX_PACKETS=120,CLOCK_HZ=27000000,BAUD=115200
)(
 input core_clk,ref_clk,global_reset_n,key0_async,ddr_init_done_async,ddr_pll_lock_async,
 input probe_started,probe_done,probe_failed,probe_init_done,
 input[7:0]probe_fault,input[3:0]probe_phase,input[1:0]probe_active_group,
 input[31:0]probe_writes,probe_reads,data_error_beats,protocol_errors,timeouts,crc_error_groups,
 input[95:0]group_count,ar_wait_min,ar_wait_max,ar_wait_sum,first_min,first_max,first_sum,last_min,last_max,last_sum,actual_crc,expected_crc,
 output telemetry_tx,output snapshot_captured_core,output snapshot_valid_ref
);
 (* PAP_ASYNC_REG=1,async_reg="true" *)reg[1:0]ref_release=0,key_sync=0,global_sync=0,init_sync=0,lock_sync=0;
 always @(posedge ref_clk)begin
  ref_release<={ref_release[0],1'b1};
  if(!ref_release[1])begin key_sync<=0;global_sync<=0;init_sync<=0;lock_sync<=0;end
  else begin key_sync<={key_sync[0],key0_async};global_sync<={global_sync[0],global_reset_n};init_sync<={init_sync[0],ddr_init_done_async};lock_sync<={lock_sync[0],ddr_pll_lock_async};end
 end
 wire dv;wire[1183:0]data;
 ddr_probe_snapshot_bridge source(
  .core_clk(core_clk),.ref_clk(ref_clk),.global_reset_n(global_reset_n),
  .probe_started(probe_started),.probe_done(probe_done),.probe_failed(probe_failed),.probe_init_done(probe_init_done),
  .probe_fault(probe_fault),.probe_phase(probe_phase),.probe_active_group(probe_active_group),.probe_writes(probe_writes),.probe_reads(probe_reads),
  .data_error_beats(data_error_beats),.protocol_errors(protocol_errors),.timeouts(timeouts),.crc_error_groups(crc_error_groups),
  .group_count(group_count),.ar_wait_min(ar_wait_min),.ar_wait_max(ar_wait_max),.ar_wait_sum(ar_wait_sum),
  .first_min(first_min),.first_max(first_max),.first_sum(first_sum),.last_min(last_min),.last_max(last_max),.last_sum(last_sum),.actual_crc(actual_crc),.expected_crc(expected_crc),
  .snapshot_captured_core(snapshot_captured_core),.snapshot_valid(dv),.snapshot(data));
 ddr_probe_uart #(.GAP_CLKS(GAP_CLKS),.MAX_PACKETS(MAX_PACKETS),.CLOCK_HZ(CLOCK_HZ),.BAUD(BAUD)) serial_out(
  .clk(ref_clk),.rst_n(ref_release[1]),.epoch_run(global_sync[1]),.live_flags({lock_sync[1],init_sync[1],global_sync[1],key_sync[1]}),
  .snapshot_valid(dv),.snapshot(data),.tx(telemetry_tx),.latest_valid(snapshot_valid_ref));
endmodule
