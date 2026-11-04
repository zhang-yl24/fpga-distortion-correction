`timescale 1ps/1ps
module tb_ddr_probe_readout;
 reg ref_clk=0,core_clk=0,core_run=1;
 always #18518 ref_clk=~ref_clk;
 always #4000 if(core_run)core_clk=~core_clk;
 reg global_reset_n=0,key0=0,ddr_init=0,ddr_lock=0;
 reg started=0,done=0,failed=0,init=0;reg[7:0]fault=0;reg[3:0]phase=0;reg[1:0]active_group=0;
 reg[31:0]writes=0,reads=0,data_error=0,protocol_error=0,timeouts=0,crc_error=0;
 reg[95:0]gc=0,wmn=0,wmx=0,wsm=0,fmn=0,fmx=0,fsm=0,lmn=0,lmx=0,lsm=0,ac=0,ec=0;
 wire tx,captured,valid_ref;
 ddr_probe_readout #(.GAP_CLKS(32),.MAX_PACKETS(6)) dut(
  .core_clk(core_clk),.ref_clk(ref_clk),.global_reset_n(global_reset_n),.key0_async(key0),.ddr_init_done_async(ddr_init),.ddr_pll_lock_async(ddr_lock),
  .probe_started(started),.probe_done(done),.probe_failed(failed),.probe_init_done(init),.probe_fault(fault),.probe_phase(phase),.probe_active_group(active_group),.probe_writes(writes),.probe_reads(reads),
  .data_error_beats(data_error),.protocol_errors(protocol_error),.timeouts(timeouts),.crc_error_groups(crc_error),
  .group_count(gc),.ar_wait_min(wmn),.ar_wait_max(wmx),.ar_wait_sum(wsm),.first_min(fmn),.first_max(fmx),.first_sum(fsm),.last_min(lmn),.last_max(lmx),.last_sum(lsm),.actual_crc(ac),.expected_crc(ec),
  .telemetry_tx(tx),.snapshot_captured_core(captured),.snapshot_valid_ref(valid_ref));
 integer file,i,g,n=0;reg[7:0]byte_value;reg[607:0]atomic_packet;reg prev_active=0;
 initial begin
  file=$fopen("readout-wire.bin","wb");if(file==0)$fatal(1,"wire output");
  while(n<480)begin
   @(negedge tx);repeat(117)@(posedge ref_clk);if(tx!==0)$fatal(1,"start8N1");
   for(i=0;i<8;i=i+1)begin repeat(234)@(posedge ref_clk);byte_value[i]=tx;end
   repeat(234)@(posedge ref_clk);if(tx!==1)$fatal(1,"stop8N1");
   $fwrite(file,"%c",byte_value);n=n+1;
  end
  $fclose(file);wait(dut.serial_out.packet_count==6);repeat(5000)@(posedge ref_clk);
  if(tx!==1 || dut.serial_out.active || dut.serial_out.packet_count!=6)$fatal(1,"finite sender");
  if(core_run!==0)$fatal(1,"core not stopped");
  $display("PGDDR_READOUT_WIRE_PASS bytes=480 packets=6 stopped_core=1 atomic_packet=1 finite=1");$finish;
 end
 always @(negedge tx)if(n>=480)$fatal(1,"extra packet after finite limit");
 always @(posedge ref_clk)begin
  if(dut.serial_out.active && !prev_active)atomic_packet<=dut.serial_out.held_payload;
  else if(dut.serial_out.active && dut.serial_out.held_payload!==atomic_packet)$fatal(1,"packet changed in flight");
  prev_active<=dut.serial_out.active;
 end
 initial begin
  wait(dut.serial_out.active && dut.serial_out.byte_index==10);
  @(negedge ref_clk);global_reset_n=1;key0=1;ddr_init=1;ddr_lock=1;
  for(g=0;g<3;g=g+1)begin
   gc[g*32+:32]=16;wmn[g*32+:32]=1+g;wmx[g*32+:32]=5+g;wsm[g*32+:32]=48+16*g;
   fmn[g*32+:32]=8+g;fmx[g*32+:32]=12+g;fsm[g*32+:32]=160+16*g;
   lmn[g*32+:32]=23+g;lmx[g*32+:32]=30+g;lsm[g*32+:32]=400+16*g;
   ac[g*32+:32]=32'hcafe0000+g;ec[g*32+:32]=32'hcafe0000+g;
  end
  started=1;init=1;phase=7;active_group=2;writes=16;reads=48;
  repeat(10)@(negedge core_clk);done=1;
  wait(captured);@(negedge core_clk);
  gc={3{32'hdeadbeef}};wmn=gc;wmx=gc;wsm=gc;fmn=gc;fmx=gc;fsm=gc;lmn=gc;lmx=gc;lsm=gc;ac=gc;ec=gc;
  writes=123;reads=456;fault=8'haa;phase=1;done=0;failed=1;
  wait(valid_ref);@(negedge core_clk);core_run=0;
  wait(dut.serial_out.packet_count==3 && dut.serial_out.active && dut.serial_out.byte_index==20);
  @(negedge ref_clk);key0=0;global_reset_n=0;ddr_init=0;ddr_lock=0;
 end
 initial begin #(64'd100000000000);$fatal(1,"readout100ms deadline bytes%0d",n);end
endmodule
