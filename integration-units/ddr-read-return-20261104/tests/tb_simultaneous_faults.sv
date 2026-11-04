`timescale 1ns/1ps
module tb_simultaneous_faults;
  reg clk=0; always #4 clk=~clk;
  reg rst_n=0;
  reg c0_valid=0, arready=0, rvalid=0, rlast=0;
  reg [3:0] rid=0;
  reg [255:0] rdata=0;
  wire [27:0] araddr; wire [3:0] arlen;
  wire arvalid, failed, busy, af, rf;
  wire [7:0] fault, ac, rc;
  wire c0_ready,c1_ready,c0_rvalid,c1_rvalid;
  wire [31:0] b0,b1;
  integration_ddr_read_return_unit #(.TIMEOUT_BITS(4)) dut(
    .clk(clk),.rst_n(rst_n),.display_urgent(1'b0),
    .c0_araddr(28'h1234),.c1_araddr(28'h5678),.c0_arlen(4'd0),.c1_arlen(4'd0),
    .c0_arvalid(c0_valid),.c1_arvalid(1'b0),.c0_arready(c0_ready),.c1_arready(c1_ready),
    .c0_rdata(),.c1_rdata(),.c0_rvalid(c0_rvalid),.c1_rvalid(c1_rvalid),
    .c0_rlast(),.c1_rlast(),.c0_rid(),.c1_rid(),
    .araddr(araddr),.arlen(arlen),.arvalid(arvalid),.arready(arready),
    .rdata(rdata),.rvalid(rvalid),.rlast(rlast),.rid(rid),
    .failed(failed),.fault(fault),.busy(busy),
    .arbiter_failed(af),.return_protocol_fault(rf),.arbiter_fault(ac),.return_fault(rc),
    .bursts0(b0),.bursts1(b1));
  initial begin
    repeat(3) @(negedge clk);
    rst_n=1; c0_valid=1;
    wait(arvalid);
    @(negedge clk); arready=1; rvalid=1; rlast=1; rid=1; rdata=256'hcafe;
    @(posedge clk); #1;
    if(failed) $fatal(1,"Fault unexpectedly early before registered RID reaches arbiter");
    @(negedge clk); arready=0; c0_valid=0; rvalid=1; rlast=1; rid=0; rdata=256'hbeef;
    @(posedge clk); #1;
    if(!failed || !af || !rf || ac!==8'h03 || rc!==8'h40 || fault!==8'h03)
      $fatal(1,"Simultaneous fault export incorrect af=%b ac=%h rf=%b rc=%h fault=%h",af,ac,rf,rc,fault);
    @(negedge clk); rvalid=0; rlast=0;
    repeat(8) begin
      @(posedge clk); #1;
      if(!af || !rf || fault!==8'h03 || c0_rvalid || c1_rvalid || arvalid || b0!=0 || b1!=0)
        $fatal(1,"Sticky faults or quarantine lost");
    end
    @(negedge clk); rst_n=0;
    @(posedge clk); #1;
    if(failed || af || rf || busy || c0_rvalid || c1_rvalid)
      $fatal(1,"Whole-domain reset did not clear faults and valid");
    $display("PASS SIMULTANEOUS_FAULT_EXPORT: bad RID arbiter=03 and raw unsolicited guard=40 assert same edge; arbiter priority, separate sticky codes, no completion counted, common reset clears.");
    $finish;
  end
  initial begin #10000; $fatal(1,"Timeout"); end
endmodule
