`timescale 1ns/1ps
module tb_dual_arbiter;
reg clk=0;always #4 clk=~clk;
reg rst_n=0,display_urgent=0;
reg [27:0] a0=0,a1=0;reg [3:0] l0=15,l1=7;
reg v0=0,v1=0,arready=0;wire q0,q1;
wire [27:0] araddr;wire [3:0] arlen;wire arvalid;
reg [255:0] rdata=0;reg rvalid=0,rlast=0;reg [3:0] rid=0;
wire [255:0] d0,d1;wire r0,r1,last0,last1;wire [3:0] id0,id1;
wire failed,busy;wire [7:0] fault;wire [31:0] bursts0,bursts1;
ddr_read_arbiter #(.TIMEOUT_BITS(6)) dut(.clk(clk),.rst_n(rst_n),.display_urgent(display_urgent),
 .c0_araddr(a0),.c1_araddr(a1),.c0_arlen(l0),.c1_arlen(l1),.c0_arvalid(v0),.c1_arvalid(v1),.c0_arready(q0),.c1_arready(q1),
 .c0_rdata(d0),.c1_rdata(d1),.c0_rvalid(r0),.c1_rvalid(r1),.c0_rlast(last0),.c1_rlast(last1),.c0_rid(id0),.c1_rid(id1),
 .araddr(araddr),.arlen(arlen),.arvalid(arvalid),.arready(arready),.rdata(rdata),.rvalid(rvalid),.rlast(rlast),.rid(rid),
 .failed(failed),.fault(fault),.busy(busy),.bursts0(bursts0),.bursts1(bursts1));
integer accepted=0,returned=0,head=0,tail=0,left=0,beat=0;
integer expected_owner[0:31],expected_length[0:31];reg [27:0] expected_addr[0:31];
reg monitor=1,held=0;reg [31:0] saved;
integer full_exchange=0,empty_fallthrough=0,peak=0;
always @(posedge clk)if(rst_n)begin
 if(held && (!arvalid || {arlen,araddr}!==saved))$fatal(1,"arb AR changed while stalled");
 held=arvalid&&!arready;saved={arlen,araddr};
 if(monitor)begin
  if(failed)$fatal(1,"unexpected arb fault %h",fault);
  if(arvalid&&arready)begin
   if(!(q0^q1))$fatal(1,"AR acknowledgement missing/ambiguous");
   expected_owner[tail]=q1;expected_length[tail]=arlen;expected_addr[tail]=araddr;tail=tail+1;accepted=accepted+1;
   if(dut.outstanding==2 && rvalid&&rlast)full_exchange=full_exchange+1;
   if(dut.outstanding==0 && rvalid)empty_fallthrough=empty_fallthrough+1;
  end
  if(rvalid)begin
   if(head>=tail)$fatal(1,"test response without accepted command");
   if((r0!==!expected_owner[head]) || (r1!==expected_owner[head]))$fatal(1,"ordered response owner mismatch head=%0d",head);
   if(rlast!==(beat==expected_length[head]) || rid!==0 || rdata[31:0]!==expected_addr[head]+beat)
     $fatal(1,"independent response data/length mismatch");
   if(rlast)begin head=head+1;returned=returned+1;beat=0;end else beat=beat+1;
  end
  if(dut.outstanding>peak)peak=dut.outstanding;
 end
end

task reset_domain;begin
 @(negedge clk);rst_n=0;v0=0;v1=0;arready=0;rvalid=0;rlast=0;rid=0;display_urgent=0;held=0;
 repeat(3)@(negedge clk);
 accepted=0;returned=0;head=0;tail=0;beat=0;monitor=1;rst_n=1;
end endtask

task issue(input integer owner,input [27:0] addr,input [3:0] len,input integer stalls);
begin
 @(negedge clk);arready=stalls==0;
 if(owner)begin a1=addr;l1=len;v1=1;end else begin a0=addr;l0=len;v0=1;end
 if(stalls!=0)begin
  while(!arvalid)@(negedge clk);
  repeat(stalls)@(negedge clk);
  arready=1;
 end
 @(posedge clk);
 while(!(arvalid&&arready))@(posedge clk);
 if(!(arvalid&&arready))$fatal(1,"issue lost handshake");
 @(negedge clk);if(owner)v1=0;else v0=0;
end endtask

task return_burst(input [27:0] addr,input integer len,input integer first);
integer k;begin
 for(k=first;k<=len;k=k+1)begin
  @(negedge clk);rvalid=1;rlast=k==len;rid=0;rdata=0;rdata[31:0]=addr+k;
  @(posedge clk);
 end
 @(negedge clk);rvalid=0;rlast=0;
end endtask

task expect_fault(input [7:0] code);begin
 @(posedge clk);#1;if(!failed || fault!==code)$fatal(1,"expected fault %h got failed=%0d fault=%h",code,failed,fault);
 @(negedge clk);rvalid=0;rlast=0;rid=0;
 repeat(3)@(negedge clk);
 if(r0||r1||q0||q1)$fatal(1,"response/client acknowledgement escaped quarantine");
end endtask
integer k;
initial begin
 reset_domain();
 issue(1,28'h100,7,3);issue(0,28'h200,15,0);
 if(dut.outstanding!==2)$fatal(1,"did not accept two before firstR");
 fork
  issue(1,28'h300,7,0);
  return_burst(28'h100,7,0);
 join
 return_burst(28'h200,15,0);return_burst(28'h300,7,0);
 repeat(2)@(negedge clk);
 if(busy||accepted!=3||returned!=3||full_exchange!=1||peak!=2||bursts0!=1||bursts1!=2)$fatal(1,"queue2 conservation/exchange");
 $display("PASS_ARB_TWO_ORDERED_FULL_POP_PUSH_ARSTALL");
 reset_domain();
 @(negedge clk);v1=1;a1=28'h400;l1=7;
 while(!arvalid)@(negedge clk);
 arready=1;rvalid=1;rlast=0;rdata=28'h400;
 @(posedge clk);
 @(negedge clk);v1=0;rvalid=0;
 return_burst(28'h400,7,1);
 repeat(2)@(negedge clk);
 if(busy||accepted!=1||returned!=1||empty_fallthrough!=1)$fatal(1,"empty fallthrough conservation");
 $display("PASS_ARB_EMPTY_ACCEPT_FIRST_R_SAME_EDGE");
 reset_domain();
 issue(1,28'h500,7,0);issue(0,28'h600,15,0);
 monitor=0;@(negedge clk);rvalid=1;rlast=0;rid=1;
 expect_fault(8'h03);
 if(dut.outstanding!==2)$fatal(1,"wrongRID destroyed live reservations");
 $display("PASS_ARB_WRONG_RID_TWO_QUARANTINE");
 reset_domain();
 issue(1,28'h700,7,0);issue(0,28'h800,15,0);
 monitor=0;@(negedge clk);rvalid=1;rlast=1;rid=0;
 expect_fault(8'h03);
 if(dut.outstanding!==2)$fatal(1,"earlyLAST released reservations");
 $display("PASS_ARB_EARLY_LAST_TWO_QUARANTINE");
 reset_domain();
 issue(1,28'h900,7,0);
 monitor=0;@(negedge clk);a0=28'ha00;l0=15;v0=1;arready=0;
 while(!arvalid)@(negedge clk);
 rvalid=1;rlast=1;rid=0;
 expect_fault(8'h03);
 if(!arvalid||araddr!==28'ha00)$fatal(1,"fault withdrew pending AR");
 @(negedge clk);arready=1;
 @(posedge clk);#1;if(arvalid)$fatal(1,"fault AR did not drain");
 $display("PASS_ARB_FAILED_AR_HELD_UNTIL_ACCEPT");
 reset_domain();
 monitor=0;@(negedge clk);a1=28'hb00;l1=7;v1=1;arready=0;
 while(!arvalid)@(negedge clk);
 rvalid=1;rlast=0;rid=0;
 expect_fault(8'h04);
 if(!arvalid)$fatal(1,"R04 withdrew stalled AR");
 @(negedge clk);arready=1;
 @(posedge clk);#1;if(arvalid)$fatal(1,"R04 AR did not drain");
 $display("PASS_ARB_R04_HELD_ADDRESS");
 reset_domain();
 issue(1,28'hc00,7,0);issue(0,28'hd00,15,0);monitor=0;
 repeat(66)@(negedge clk);
 if(!failed||fault!==8'h01||dut.outstanding!==2)$fatal(1,"two-reservation timeout");
 $display("PASS_ARB_TIMEOUT_TWO_QUARANTINE");
 reset_domain();issue(1,28'he00,7,0);issue(0,28'hf00,15,0);
 reset_domain();
 if(busy||failed||dut.outstanding!==0)$fatal(1,"coordinated reset did not clear all leases");
 @(negedge clk);display_urgent=1;v0=1;v1=1;a0=28'h1000;a1=28'h1100;arready=0;
 while(!arvalid)@(negedge clk);
 if(araddr!==28'h1000)$fatal(1,"display urgency ignored");
 arready=1;@(posedge clk);@(negedge clk);v0=0;v1=0;
 $display("PASS_ARB_RESET_TWO_AND_DISPLAY_URGENT");
 $display("PASS_DUAL_ARBITER cases=8");$finish;
end
initial begin #200000;$fatal(1,"arbiter TB watchdog");end
endmodule
