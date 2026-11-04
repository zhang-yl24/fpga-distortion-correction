`timescale 1ns/1ps
// Actual control system with the scheduler engine stub held idle.
module tb_system_readstage_guard;
 reg clk=0;always #4 clk=~clk;reg pix=0;always #3.367 pix=~pix;
 reg rst_n=0,rv=0;wire failed;wire [7:0] fault;wire av,wv;
 wire [2:0] reserved;
 hdmi_camera_fisheye_system #(.WIDTH(32),.HEIGHT(16),.BANK_STRIDE(512),.HT(80),.VT(40),.HS(4),.VS(1),.X0(10),.Y0(3)) dut(
  .core_clk(clk),.pix_in_clk(pix),.pix_out_clk(pix),.rst_n(rst_n),.capture_admit(1'b0),.scan_enable(1'b0),
  .external_fault(1'b0),.external_fault_code(8'd0),.pix_in_vsync_active(1'b0),.pix_in_de(1'b0),.pix_in_rgb(24'd0),.cfg_corrected(1'b1),
  .awvalid(wv),.arvalid(av),.awready(1'b0),.arready(1'b0),.wready(1'b0),.wlast(1'b0),
  .rdata(256'hbad),.rvalid(rv),.rlast(1'b1),.rid(4'd0),.failed(failed),.fault(fault),.capture_reserved(reserved));
 task automatic common_reset;
  begin
   @(negedge clk);rst_n=0;rv=1;repeat(8)@(negedge clk);rv=0;rst_n=1;repeat(12)@(negedge clk);
   if(failed || fault || av || wv || reserved || dut.staged_rvalid)$fatal(1,"reset/control state differs");
  end
 endtask
 initial begin
  common_reset();rv=1;@(negedge clk);rv=0;repeat(10)@(negedge clk);
  if(!failed || fault!=8'h40 || !dut.read_stage_failed || !dut.stop_admit || !dut.system_failed)
   $fatal(1,"system did not latch raw owner fault code=%h",fault);
  repeat(30)begin
   @(negedge clk);rv=!rv;
   if(!failed || fault!=8'h40 || dut.sample_rvalid || dut.display_rvalid || av || wv || reserved)
    $fatal(1,"fault quarantine leaked traffic or changed cause");
  end
  common_reset();repeat(30)@(negedge clk);
  if(failed || fault)$fatal(1,"common reset did not restore clean epoch");
  $display("PASS SYSTEM READSTAGE raw-no-owner sticky40 stop-admit no-client-valid common-reset");$finish;
 end
 initial begin #100000;$fatal(1,"system guard timeout");end
endmodule
