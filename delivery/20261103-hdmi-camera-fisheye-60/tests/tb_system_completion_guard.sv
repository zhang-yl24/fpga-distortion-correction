`timescale 1ns/1ps
// Actual controller and bank. Reader/scan completion boundaries are driven
// as held bundles to isolate protocol faults; engine is the idle stub.
module tb_system_completion_guard;
 reg clk=0,pix=0,rst_n=0;always #4 clk=~clk;always #3.367 pix=~pix;
 reg ext=0;wire failed;wire[7:0]fault;
 reg req=0,ack=0,done=0,rdone=0,ridle=1,pgood=1,pbank=1;
 reg[31:0]epoch=0,pid=0,pepoch=0,pcrc=0,pcount=512,rbeats=32,rcrc=0;
 reg[9:0]used=0;
 integer cases=0,releases=0,old_good=0,old_new=0,old_repeat=0,accept_now;
 hdmi_camera_fisheye_system #(.WIDTH(32),.HEIGHT(16),.BANK_STRIDE(512),.HT(80),.VT(40),.HS(4),.VS(1),.X0(10),.Y0(3)) dut(
  .core_clk(clk),.pix_in_clk(pix),.pix_out_clk(pix),.rst_n(rst_n),.capture_admit(1'b0),.scan_enable(1'b1),
  .external_fault(ext),.external_fault_code(8'he1),.pix_in_vsync_active(1'b0),.pix_in_de(1'b0),.pix_in_rgb(24'd0),.cfg_corrected(1'b1),
  .awready(1'b0),.arready(1'b0),.wready(1'b0),.wlast(1'b0),.rdata(256'd0),.rvalid(1'b0),.rlast(1'b0),.rid(4'd0),.failed(failed),.fault(fault));
 initial begin
  force dut.scan_request_toggle=req;force dut.scan_request_epoch=epoch;force dut.scan_grant_ack=ack;
  force dut.pix_done_toggle=done;force dut.pix_done_good=pgood;force dut.scan_done_id=pid;force dut.scan_done_bank=pbank;
  force dut.scan_done_epoch=pepoch;force dut.pix_done_crc=pcrc;force dut.consumed_pixels=pcount;force dut.scan_failed=0;
  force dut.reader_start=0;force dut.reader_done=rdone;force dut.reader_beats=rbeats;force dut.reader_checksum=rcrc;
  force dut.reader_idle=ridle;force dut.fifo_used=used;
 end
 // Every statistics increment must correspond to the SAME edge accepted
 // by the actual bank; a prepared pulse alone is never an accepted event.
 always @(posedge clk)begin
  if(!dut.cr)begin old_good=0;old_new=0;old_repeat=0;end
  else begin
   accept_now=dut.bank_release_accept;
   if(accept_now && (!dut.bank_core.display_active || dut.bank_core.display_grant_valid ||
       dut.display_done_bank!=dut.bank_core.front_bank || failed))$fatal(1,"release did not match actual bank acceptance");
   #1;
   if(dut.scan_good_frames!=old_good+accept_now ||
      dut.presented_frames+dut.scan_repeat_frames!=old_new+old_repeat+accept_now)
      $fatal(1,"statistics moved without same-edge bank release");
   if(accept_now)begin if(dut.bank_core.display_active)$fatal(1,"bank did not consume release");releases=releases+1;end
   old_good=dut.scan_good_frames;old_new=dut.presented_frames;old_repeat=dut.scan_repeat_frames;
  end
 end
 task reset_all;
  begin
   @(negedge clk);rst_n=0;ext=0;req=0;ack=0;done=0;rdone=0;ridle=1;used=0;epoch=0;
   pid=0;pepoch=0;pcrc=0;pcount=512;pbank=1;pgood=1;rbeats=32;rcrc=0;
   repeat(8)@(negedge clk);rst_n=1;repeat(8)@(negedge clk);
   if(failed || dut.lease_active || dut.pixel_check_pending || dut.reader_check_pending || dut.display_done_valid)
    $fatal(1,"common reset left completion ownership");
  end
 endtask
 task lease(input integer id,input integer grant_ack);
  begin
   @(negedge clk);dut.bank_core.front_valid=1;dut.bank_core.front_bank=1;
   dut.bank_core.front_id=id;dut.bank_core.front_crc=32'h1234abcd;
   epoch=epoch+1;req=!req;
   wait(dut.lease_active);repeat(3)@(negedge clk);
   if(dut.lease_id!=id || dut.lease_crc!=32'h1234abcd || !dut.display_active)$fatal(1,"real bank grant lease differs");
   if(grant_ack)begin ack=dut.grant_toggle;repeat(4)@(negedge clk);end
  end
 endtask
 task reader(input integer bad);
  begin
   @(negedge clk);rbeats=bad==2?31:32;rcrc=32'h1234abcd^(bad==1);rdone=1;
   @(negedge clk);rdone=0;rbeats=32'hdeadbeef;rcrc=0;
  end
 endtask
 task pixel(input integer bad,input integer wait_ack);
  reg token;
  begin
   @(negedge clk);pid=dut.lease_id^(bad==2);pepoch=dut.lease_epoch^(bad==4);
   pbank=1^(bad==3);pcrc=32'h1234abcd^(bad==1);pcount=bad==5?511:512;pgood=bad!=6;
   done=!done;token=done;
   if(wait_ack)begin
    wait(dut.pixel_finished);@(negedge clk);
    if(dut.done_ack_toggle==token)$fatal(1,"ACK preceded field validation");
    wait(dut.done_ack_toggle==token);@(negedge clk);
    pid=32'hdeadbeef;pepoch=0;pbank=0;pcrc=0;pcount=0;pgood=0;
   end
  end
 endtask
 task good(input integer expected_new,input integer expected_repeat);
  begin
   repeat(16)@(negedge clk);
   if(failed || dut.lease_active || dut.display_active || dut.presented_frames!=expected_new ||
      dut.scan_repeat_frames!=expected_repeat || dut.scan_good_frames!=expected_new+expected_repeat)
    $fatal(1,"healthy completion did not release exactly once code=%h",fault);
   cases=cases+1;
  end
 endtask
 task bad(input[7:0]code);
  begin
   repeat(16)@(negedge clk);
   if(!failed || fault!=code || dut.scan_good_frames!=0 || dut.presented_frames!=0 || dut.scan_repeat_frames!=0 ||
      dut.bank_release_accept || (dut.lease_active && !dut.display_active))
    $fatal(1,"bad completion released/count leaked code=%h expected=%h",fault,code);
   cases=cases+1;
  end
 endtask
 integer k;
 initial begin
  reset_all();lease(17,1);reader(0);pixel(0,1);good(1,0);
  lease(17,1);pixel(0,1);reader(0);good(1,1);
  lease(18,1);reader(0);pixel(0,1);good(2,1);
  reset_all();lease(17,0);reader(0);pixel(0,1);repeat(10)@(negedge clk);
  if(!dut.lease_active || dut.scan_good_frames || !dut.response_busy)$fatal(1,"grant ACK backpressure released lease");
  ack=dut.grant_toggle;good(1,0);
  for(k=1;k<=6;k=k+1)begin reset_all();lease(17,1);reader(0);pixel(k,1);bad(8'hb3);end
  for(k=1;k<=2;k=k+1)begin reset_all();lease(17,1);reader(k);pixel(0,1);bad(8'hb2);end
  reset_all();lease(17,1);reader(0);reader(0);bad(8'hb2);
  reset_all();lease(17,1);pixel(0,1);pixel(0,0);bad(8'hb3);
  reset_all();pixel(0,0);bad(8'hb3);
  reset_all();reader(0);bad(8'hb2);
  reset_all();lease(17,1);reader(0);pixel(0,0);wait(dut.pixel_check_pending!=0);reset_all();
  repeat(12)@(negedge clk);if(failed || dut.done_ack_toggle || dut.scan_good_frames)$fatal(1,"reset leaked pending completion");cases=cases+1;
  lease(17,1);reader(0);pixel(0,1);good(1,0);
  reset_all();lease(17,1);reader(0);pixel(0,1);wait(dut.display_done_valid);@(negedge clk);ext=1;bad(8'he1);
  reset_all();lease(17,1);reader(0);pixel(0,1);wait(dut.display_done_valid);@(negedge clk);used=1;bad(8'hb4);
  reset_all();lease(17,1);reader(0);pixel(0,1);wait(dut.display_done_valid);@(negedge clk);dut.bank_core.front_bank=0;bad(8'hb4);
  reset_all();lease(17,1);reader(0);pixel(0,1);wait(dut.display_done_valid);@(negedge clk);rdone=1;@(negedge clk);rdone=0;bad(8'hb2);
  if(cases!=22)$fatal(1,"completion coverage count %0d",cases);
  $display("PASS SYSTEM COMPLETION cases=%0d actual_bank_releases=%0d fields_crc_id_bank_epoch_count_good duplicates_unowned reset held_bundles ack_backpressure late_fault drain_change",cases,releases);$finish;
 end
 initial begin #200000;$fatal(1,"completion test timeout cases=%0d fault=%h",cases,fault);end
endmodule
