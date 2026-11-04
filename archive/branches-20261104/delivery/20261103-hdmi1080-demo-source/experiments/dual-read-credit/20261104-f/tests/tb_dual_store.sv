`timescale 1ns/1ps
module tb_dual_store;
reg clk=0;always #4 clk=~clk;reg rst_n=0,abort=0;
reg iv=0;wire ir;reg signed [23:0] ix=0,iy=0;reg [23:0] tag=0;
wire ov;reg ore=1;wire [23:0] p00,p10,p01,p11,otag;wire [7:0] fx,fy;
reg fv=0,safe=1;wire fr,busy,done;reg [27:0] base=0;reg [12:0] row=0,col=0;reg [31:0] ticket=0;
wire [24:0] block;wire [31:0] cticket;wire [27:0] araddr;wire [3:0] arlen;wire arvalid;reg arready=0;
reg [255:0] rdata=0;reg rv=0,rl=0;reg [3:0] rid=0;wire failed;wire [7:0] fault;
quad_parity_prefetch_store #(.WIDTH(1920),.HEIGHT(1080),.INDEX_BITS(6),.TAG_W(24),.TIMEOUT_BITS(6),.SCATTER8(1),.SCATTER16(1),.STREAM_FILL(1)) dut(
 .clk(clk),.rst_n(rst_n),.abort(abort),.in_valid(iv),.in_ready(ir),.in_x(ix),.in_y(iy),.in_tag(tag),
 .out_valid(ov),.out_ready(ore),.p00(p00),.p10(p10),.p01(p01),.p11(p11),.fx(fx),.fy(fy),.out_tag(otag),
 .fill_valid(fv),.fill_ready(fr),.fill_safe(safe),.fill_base(base),.fill_row(row),.fill_col_block(col),.fill_ticket(ticket),
 .fill_busy(busy),.fill_done(done),.completed_block(block),.completed_ticket(cticket),
 .araddr(araddr),.arlen(arlen),.arvalid(arvalid),.arready(arready),.rdata(rdata),.rvalid(rv),.rlast(rl),.rid(rid),.failed(failed),.fault(fault));
function automatic [15:0] raw(input integer p);raw=(p*109)^32'h529b^(p>>3);endfunction
function automatic [23:0] expand(input [15:0] p);expand={p[15:11],p[15:13],p[10:5],p[10:9],p[4:0],p[4:2]};endfunction
function automatic [255:0] beatdata(input integer address,beat);integer lane;begin
 for(lane=0;lane<16;lane=lane+1)beatdata[lane*16+:16]=raw(address*2+beat*16+lane);
end endfunction
integer nfill=0,ndone=0,nquery=0,nout=0,run=0,peak=0;
reg [31:0] expect_ticket[0:31];reg [24:0] expect_block[0:31];reg monitor=1,held=0;reg [31:0] saved;
always @(posedge clk)if(rst_n)begin
 if(held&&(!arvalid||{arlen,araddr}!==saved))$fatal(1,"store AR hold");held=arvalid&&!arready;saved={arlen,araddr};
 if(monitor)begin
  if(failed)$fatal(1,"unexpected store fault %h",fault);
  if(fv&&fr)begin expect_ticket[nfill]=ticket;expect_block[nfill]=row*15+col;nfill=nfill+1;end
  if(done)begin
   if(ndone>=nfill||cticket!==expect_ticket[ndone]||block!==expect_block[ndone])$fatal(1,"store ordered ticket/block completion");ndone=ndone+1;
  end
  if(iv&&ir)nquery=nquery+1;
  if(ov&&ore)begin
   if(otag!==nout||p00!==expand(raw(nout))||p10!==expand(raw(nout+1))||p01!==expand(raw(1920+nout))||p11!==expand(raw(1921+nout))||fx!==8'd19||fy!==8'd71)
    $fatal(1,"store independent query oracle/tag/fraction n=%0d",nout);
   nout=nout+1;run=run+1;if(run>peak)peak=run;
  end else run=0;
 end else if(done||ov)$fatal(1,"completion escaped store quarantine");
end

task reset_domain;begin
 @(negedge clk);rst_n=0;abort=0;iv=0;fv=0;arready=0;rv=0;rl=0;rid=0;held=0;monitor=1;
 repeat(3)@(negedge clk);nfill=0;ndone=0;nquery=0;nout=0;run=0;peak=0;rst_n=1;
end endtask

task fill(input integer y,input [31:0] t);begin
 @(negedge clk);row=y;col=0;ticket=t;fv=1;
 @(posedge clk);while(!fr)@(posedge clk);
 @(negedge clk);fv=0;
end endtask

task accept_address(input [27:0] expected);begin
 @(negedge clk);arready=0;
 while(!arvalid)@(negedge clk);
 if(araddr!==expected||arlen!==7)$fatal(1,"store AR independent address/length");
 arready=1;@(posedge clk);
 @(negedge clk);arready=0;
end endtask

task send(input integer address,startbeat);integer k;begin
 for(k=startbeat;k<8;k=k+1)begin
  @(negedge clk);rv=1;rl=k==7;rid=0;rdata=beatdata(address,k);@(posedge clk);
 end
 @(negedge clk);rv=0;rl=0;
end endtask

task fault_check(input [7:0] code);begin
 @(posedge clk);#1;if(!failed||fault!==code)$fatal(1,"store expected fault %h got %h",code,fault);
 @(negedge clk);rv=0;rl=0;rid=0;
 repeat(3)@(negedge clk);
 if(fr||ir||ov||done)$fatal(1,"store quarantine ready/publication");
end endtask
integer i;
initial begin
 reset_domain();fill(0,32'h101);fill(1,32'h102);
 if(fr||dut.fill_count!==2)$fatal(1,"store whole-burst reservations missing");
 accept_address(0);accept_address(960);
 send(0,0);send(960,0);
 while(ndone!=2)@(negedge clk);
 for(i=0;i<32;i=i+1)begin
  @(negedge clk);iv=1;ix=i*256+19;iy=71;tag=i;
  @(posedge clk);if(!ir)$fatal(1,"hot store query could not sustain II1");
 end
 @(negedge clk);iv=0;
 while(nout!=32)@(negedge clk);
 if(busy||ndone!=2||nquery!=32||peak<28)$fatal(1,"store success conservation");
 $display("PASS_STORE_TWO_BUFFERS_ORDERED_TICKETS_PIXELS_HOT_II1 run=%0d",peak);
 reset_domain();fill(0,32'h201);
 while(!arvalid)@(negedge clk);
 arready=1;rv=1;rl=0;rdata=beatdata(0,0);
 @(posedge clk);@(negedge clk);arready=0;rv=0;
 fill(1,32'h202);accept_address(960);
 send(0,1);send(960,0);while(ndone!=2)@(negedge clk);
 $display("PASS_STORE_ACCEPT_FIRST_R_SAME_EDGE");
 reset_domain();fill(0,32'h301);fill(1,32'h302);accept_address(0);accept_address(960);monitor=0;
 @(negedge clk);rv=1;rid=1;rl=0;fault_check(8'h03);
 if(dut.live!==2'b11||dut.fill_count!==2)$fatal(1,"wrongRID erased reserved buffers");
 $display("PASS_STORE_WRONG_RID_TWO_RESERVED");
 reset_domain();fill(0,32'h401);fill(1,32'h402);accept_address(0);accept_address(960);monitor=0;
 @(negedge clk);rv=1;rid=0;rl=1;fault_check(8'h03);
 if(dut.live!==2'b11||dut.fill_count!==2)$fatal(1,"earlyLAST erased reserved buffers");
 $display("PASS_STORE_EARLY_LAST_TWO_RESERVED");
 reset_domain();fill(0,32'h501);fill(1,32'h502);accept_address(0);accept_address(960);monitor=0;
 repeat(66)@(negedge clk);
 if(!failed||fault!==8'h01||dut.live!==2'b11)$fatal(1,"store timeout two reservations");
 $display("PASS_STORE_TIMEOUT_TWO_RESERVED");
 reset_domain();fill(0,32'h601);fill(1,32'h602);accept_address(0);monitor=0;
 while(!arvalid)@(negedge clk);
 abort=1;fault_check(8'h49);
 if(!arvalid||araddr!==960||dut.live!==2'b11)$fatal(1,"abort withdrew AR or owner");
 @(negedge clk);arready=1;@(posedge clk);#1;if(arvalid)$fatal(1,"aborted AR did not drain");
 $display("PASS_STORE_ABORT_TWO_HELD_AR");
 reset_domain();fill(0,32'h701);monitor=0;while(!arvalid)@(negedge clk);
 rv=1;rl=0;rid=0;fault_check(8'h04);
 if(!arvalid)$fatal(1,"R04 withdrew store address");
 @(negedge clk);arready=1;@(posedge clk);#1;if(arvalid)$fatal(1,"R04 address did not drain");
 $display("PASS_STORE_R04_HELD_AR");
 reset_domain();fill(0,32'h801);fill(1,32'h802);accept_address(0);accept_address(960);reset_domain();
 if(busy||failed||dut.live!==0||dut.fill_count!==0)$fatal(1,"coordinated store reset");
 $display("PASS_STORE_COORDINATED_RESET_TWO");
 $display("PASS_DUAL_STORE cases=8");$finish;
end
initial begin #300000;$fatal(1,"store TB watchdog");end
endmodule
