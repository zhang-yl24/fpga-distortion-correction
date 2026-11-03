`timescale 1ns/1ps
// All external pins compare every rising and falling edge. Directed assertions
// also check the published protocol without relying on the old RTL as oracle.
module tb_fill8r2_read_arbiter_compare;
reg clk=0;always #4 clk=~clk;
reg rst_n=0,urgent=0,v0=0,v1=0,ready=0,rv=0,last=0;
reg [27:0] a0=28'h1000,a1=28'h2000;
reg [3:0] l0=0,l1=0,rid=0;
reg [255:0] data=0;
wire [1:0] ready0,ready1,rv0,rv1,last0,last1,valid,failed,busy;
wire [255:0] d0[0:1],d1[0:1];wire [3:0] id0[0:1],id1[0:1],length[0:1];
wire [27:0] address[0:1];wire [7:0] fault[0:1];wire [31:0] b0[0:1],b1[0:1];
`define PORTS(i) .clk(clk),.rst_n(rst_n),.display_urgent(urgent), \
 .c0_araddr(a0),.c1_araddr(a1),.c0_arlen(l0),.c1_arlen(l1),.c0_arvalid(v0),.c1_arvalid(v1), \
 .c0_arready(ready0[i]),.c1_arready(ready1[i]),.c0_rdata(d0[i]),.c1_rdata(d1[i]), \
 .c0_rvalid(rv0[i]),.c1_rvalid(rv1[i]),.c0_rlast(last0[i]),.c1_rlast(last1[i]),.c0_rid(id0[i]),.c1_rid(id1[i]), \
 .araddr(address[i]),.arlen(length[i]),.arvalid(valid[i]),.arready(ready), \
 .rdata(data),.rvalid(rv),.rlast(last),.rid(rid),.failed(failed[i]),.fault(fault[i]),.busy(busy[i]),.bursts0(b0[i]),.bursts1(b1[i])
baseline_read_arbiter #(.TIMEOUT_BITS(4)) old_dut(`PORTS(0));
candidate_read_arbiter #(.TIMEOUT_BITS(4)) new_dut(`PORTS(1));
`undef PORTS
integer comparisons=0,random_cycles=0,samecycle=0,fault_cases=0,reset_cases=0;
reg initialized=0;
task compare;
begin
 if(initialized)begin
  if({ready0[0],ready1[0],d0[0],d1[0],rv0[0],rv1[0],last0[0],last1[0],id0[0],id1[0],
      address[0],length[0],valid[0],failed[0],fault[0],busy[0],b0[0],b1[0]} !==
     {ready0[1],ready1[1],d0[1],d1[1],rv0[1],rv1[1],last0[1],last1[1],id0[1],id1[1],
      address[1],length[1],valid[1],failed[1],fault[1],busy[1],b0[1],b1[1]})
   $fatal(1,"external old/new pin difference t=%0t",$time);
  comparisons=comparisons+1;
 end
end
endtask
always @(posedge clk)begin #1;compare;end
always @(negedge clk)begin #2;compare;end
task tick;begin @(posedge clk);#2;@(negedge clk);end endtask
task reset;
begin
 rst_n=0;v0=0;v1=0;ready=0;rv=0;last=0;rid=0;urgent=0;l0=0;l1=0;
 repeat(3)tick;initialized=1;rst_n=1;tick;
 if(failed[1]||busy[1]||fault[1]!=0||b0[1]!=0||b1[1]!=0)$fatal(1,"reset contract");
 reset_cases=reset_cases+1;
end
endtask
task address0(input [3:0] beats_minus1);
begin
 l0=beats_minus1;v0=1;tick;v0=0;
 if(!valid[1]||address[1]!=a0||length[1]!=beats_minus1)$fatal(1,"saved AR contract");
end
endtask
task sticky(input [7:0] expected);
integer n;
begin
 if(!failed[1]||fault[1]!=expected)$fatal(1,"wrong first fault code expected=%h got=%h",expected,fault[1]);
 ready=1;rv=1;last=0;rid=15;v0=1;v1=1;
 for(n=0;n<20;n=n+1)begin
  #1;if(rv0[1]||rv1[1]||ready0[1]||ready1[1])$fatal(1,"quarantine routed client traffic");
  tick;if(!failed[1]||fault[1]!=expected)$fatal(1,"sticky first fault changed");
 end
 fault_cases=fault_cases+1;
end
endtask
integer n,k,fd;reg [31:0] rng=32'hc0ffee51;
task randomize_bus;
begin
 rng=rng^(rng<<13);rng=rng^(rng>>17);rng=rng^(rng<<5);
 v0=rng[0];v1=rng[1];urgent=rng[2];ready=rng[3];rv=rng[4];last=rng[5];
 rid=rng[10:7];l0=rng[14:11];l1=rng[18:15];a0={rng[27:5],5'b0};a1={rng[31:9],5'b0};data={8{rng}};
end
endtask
initial begin
 @(negedge clk);reset;
 // First response and address acceptance share the same edge, both owners.
 address0(1);repeat(6)begin tick;if(!valid[1]||address[1]!=a0)$fatal(1,"stalled AR changed");end
 ready=1;rv=1;last=0;data=256'h1234;#1;
 if(!ready0[1]||ready1[1]||!rv0[1]||rv1[1]||d0[1]!=data)$fatal(1,"same cycle first response owner0");
 samecycle=samecycle+1;tick;ready=0;rv=0;repeat(3)tick;
 rv=1;last=1;data=256'habcd;#1;if(!rv0[1]||d0[1]!=data)$fatal(1,"second beat");
 tick;rv=0;if(b0[1]!=1||busy[1])$fatal(1,"burst completion");
 l1=0;v1=1;tick;v1=0;ready=1;rv=1;last=1;#1;
 if(!ready1[1]||ready0[1]||!rv1[1]||rv0[1])$fatal(1,"same cycle single response owner1");
 samecycle=samecycle+1;tick;ready=0;rv=0;
 if(b1[1]!=1||failed[1]||busy[1])$fatal(1,"single beat completion");
 // Wrong RID, early RLAST, absent RLAST, timeout, idle unsolicited.
 reset;address0(0);ready=1;rv=1;last=1;rid=1;tick;sticky(3);
 reset;address0(1);ready=1;rv=1;last=1;tick;sticky(3);
 reset;address0(0);ready=1;rv=1;last=0;tick;sticky(3);
 reset;address0(7);ready=1;tick;ready=0;rv=0;repeat(18)tick;sticky(1);
 reset;rv=1;tick;sticky(4);
 // A stray R during stalled AR cannot retract the visible command. Later AR
 // acceptance quarantines without acknowledging the client or adding a fault.
 reset;address0(7);ready=0;rv=1;last=1;tick;
 if(!failed[1]||fault[1]!=4)$fatal(1,"stalled ADDRESS stray not diagnosed");
 repeat(20)begin tick;if(!valid[1]||address[1]!=a0||length[1]!=7)$fatal(1,"fault withdrew stalled AR");end
 ready=1;#1;if(ready0[1]||ready1[1])$fatal(1,"failed AR acknowledged client");tick;
 if(valid[1])$fatal(1,"accepted failed AR not quarantined");sticky(4);
 // Warm reset while the command is stalled and while a response is pending.
 reset;address0(15);reset;address0(15);ready=1;tick;ready=0;reset;
 // Deterministic arbitrary per-cycle traffic, including malformed handshakes
 // and repeated fault-domain resets. Every externally visible pin compares.
 for(k=0;k<100;k=k+1)begin
  reset;
  for(n=0;n<200;n=n+1)begin randomize_bus;tick;random_cycles=random_cycles+1;end
 end
 fd=$fopen("comparison-summary.json","w");
 $fdisplay(fd,"{\"passed\":true,\"pin_comparisons\":%0d,\"random_cycles\":%0d,\"samecycle_responses\":%0d,\"fault_cases\":%0d,\"reset_cases\":%0d}",comparisons,random_cycles,samecycle,fault_cases,reset_cases);
 $fclose(fd);$display("PASS fill8r2 read arbiter per-cycle independent protocol and equivalence regression");$finish;
end
initial begin #2000000;$fatal(1,"comparison timeout");end
endmodule
