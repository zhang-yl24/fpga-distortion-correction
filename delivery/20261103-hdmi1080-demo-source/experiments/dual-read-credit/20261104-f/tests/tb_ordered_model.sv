`timescale 1ns/1ps
module tb_ordered_model;
reg clk=0;always #4 clk=~clk;reg rst_n=0;
reg [27:0] araddr=0,awaddr=28'h10000;reg [3:0] arlen=7,awlen=3;reg arvalid=0,awvalid=0;
wire arready,awready,rvalid,rlast,wready,wlast;wire [3:0] rid;wire [255:0] rdata,memdata,wdata,mwd;
wire [31:0] mws;wire [27:0] ma,mwa;wire mwe,refa,stopa;
wire [63:0] tick,nar,naw,nr,nw,nref,nstop,nturn;
integer wc=0,accepted=0,head=0,beat=0,returned=0,full_exchange=0;
reg [27:0] ea[0:7];reg [63:0] atick[0:7],first_tick[0:7],last_tick[0:7];
assign memdata={8{4'h0,ma}};assign wdata={8{32'hdead0000+wc}};
ddr_ordered_two_credit_model #(.R_LATENCY(8)) dut(.clk(clk),.rst_n(rst_n),
 .araddr(araddr),.arlen(arlen),.arvalid(arvalid),.arready(arready),.awaddr(awaddr),.awlen(awlen),.awvalid(awvalid),.awready(awready),
 .rdata(rdata),.rvalid(rvalid),.rlast(rlast),.rid(rid),.wdata(wdata),.wstrb(32'hffffffff),.wready(wready),.wlast(wlast),
 .mem_raddr(ma),.mem_rdata(memdata),.mem_waddr(mwa),.mem_we(mwe),.mem_wdata(mwd),.mem_wstrb(mws),
 .refresh_active(refa),.stop_active(stopa),.tick(tick),.read_commands(nar),.write_commands(naw),.read_beats(nr),.write_beats(nw),.refresh_cycles(nref),.stop_cycles(nstop),.turn_wait_cycles(nturn));
reg check=1;reg [27:0] response_address;
always @(posedge clk)if(rst_n&&check)begin
 if(arvalid&&arready)begin
  ea[accepted]=araddr;atick[accepted]=tick;accepted=accepted+1;
  if(dut.qcount==2&&rvalid&&rlast)full_exchange=full_exchange+1;
 end
 if(rvalid)begin
  response_address=ea[head]+beat*8;
  if(head>=accepted||rdata!=={8{4'h0,response_address}}||rid!==0||rlast!==(beat==7))$fatal(1,"model independent R data/order/last");
  if(tick<atick[head]+9)$fatal(1,"model returned before fixed per-command delay");
  if(beat==0)first_tick[head]=tick;
  if(rlast)begin last_tick[head]=tick;head=head+1;returned=returned+1;beat=0;end else beat=beat+1;
 end
 if(wready)begin
  if(!mwe||mwa!==28'h10000+wc*8||mwd!=={8{32'hdead0000+wc}}||mws!==32'hffffffff||wlast!==(wc==3))$fatal(1,"model write identity/address/last");
  if(rvalid)$fatal(1,"model shared bus overlap");wc=wc+1;
 end
end

task issue(input [27:0] address);begin
 @(negedge clk);araddr=address;arvalid=1;
 @(posedge clk);while(!arready)@(posedge clk);
 @(negedge clk);arvalid=0;
end endtask
initial begin
 repeat(4)@(negedge clk);rst_n=1;
 issue(28'h100);issue(28'h200);
 if(dut.qcount!==2)$fatal(1,"model did not queue two AR before R");
 fork
  issue(28'h300);
  begin
   @(negedge clk);awvalid=1;@(posedge clk);while(!awready)@(posedge clk);@(negedge clk);awvalid=0;
  end
 join
 while(returned!=3||wc!=4)@(negedge clk);
 if(first_tick[0]!==atick[0]+9||first_tick[1]!==last_tick[0]+1||first_tick[2]!==atick[2]+9||
  full_exchange!=1||nar!=3||nr!=24||naw!=1||nw!=4||dut.qcount!=0||dut.wpending||dut.latency_overlap_commands==0)
   $fatal(1,"model timing/overlap/conservation first0=%0d accept0=%0d first1=%0d last0=%0d first2=%0d accept2=%0d full=%0d",first_tick[0],atick[0],first_tick[1],last_tick[0],first_tick[2],atick[2],full_exchange);
 $display("PASS_QUEUED_MODEL_FIXED_DELAY_ORDER_SHARED_BUS_FULL_POP_PUSH AR=3 R=24 AW=1 W=4 first0=%0d first1=%0d first2=%0d",first_tick[0],first_tick[1],first_tick[2]);
 check=0;issue(28'h400);issue(28'h500);
 @(negedge clk);rst_n=0;repeat(3)@(negedge clk);rst_n=1;
 if(dut.qcount!==0||dut.wpending||rvalid||wready)$fatal(1,"model reset did not flush two commands");
 repeat(16)@(negedge clk);if(rvalid||nar!=0||nr!=0)$fatal(1,"model old response after coordinated reset");
 $display("PASS_QUEUED_MODEL_RESET_TWO_PENDING");$finish;
end
initial begin #100000;$fatal(1,"model TB watchdog");end
endmodule
