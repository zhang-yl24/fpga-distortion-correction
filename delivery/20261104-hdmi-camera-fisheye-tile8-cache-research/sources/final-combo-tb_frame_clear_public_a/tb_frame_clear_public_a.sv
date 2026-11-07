`timescale 1ns/1ps
module tb_frame_clear_public_a;
 reg clk=0;always #4 clk=~clk;
 reg rst_n=0,frame_valid=0,in_valid=0;
 reg [27:0] frame_base=0;
 reg signed [23:0] in_x=13,in_y=37;
 reg [24:0] in_tag=0;
 wire frame_ready,in_ready,out_valid,failed,arvalid;
 wire [23:0] p00,p10,p01,p11;wire [7:0] fx,fy,fault;
 wire [24:0] out_tag;wire [27:0] araddr;wire [3:0] arlen;
 wire [31:0] hits,misses,completed_queries;
 reg arready=0,rvalid=0,rlast=0;reg [255:0] rdata=0;
 integer left=0,beat=0,start_pixel=0,burst_epoch=0,current_epoch=0;
 integer frames=0,admitted=0,outputs=0,blocked=0,clears=0,fd;
 ddr_neighbour_cache_scatter16_rowpipe #(.WIDTH(128),.HEIGHT(1080),.INDEX_BITS(10),.TAG_W(25),.TIMEOUT_BITS(12)) dut(
 .clk(clk),.rst_n(rst_n),.frame_valid(frame_valid),.frame_ready(frame_ready),.frame_base(frame_base),
 .in_valid(in_valid),.in_ready(in_ready),.in_x(in_x),.in_y(in_y),.in_tag(in_tag),
 .out_valid(out_valid),.out_ready(1'b1),.p00(p00),.p10(p10),.p01(p01),.p11(p11),.fx(fx),.fy(fy),.out_tag(out_tag),
 .araddr(araddr),.arlen(arlen),.arvalid(arvalid),.arready(arready),.rdata(rdata),.rvalid(rvalid),.rlast(rlast),.rid(4'd0),
 .failed(failed),.fault(fault),.hits(hits),.misses(misses),.completed_queries(completed_queries));
 function automatic [15:0] source(input integer p,e);source=(p*197+(p>>3)*29+16'h6351+e*16'h123b)&65535;endfunction
 function automatic [23:0] expand(input [15:0] p);expand={p[15:11],p[15:13],p[10:5],p[10:9],p[4:0],p[4:2]};endfunction
 always @(negedge clk)begin
  arready=rst_n&&left==0;rvalid=rst_n&&left>0;rlast=left==1;
  for(integer n=0;n<16;n=n+1)rdata[n*16+:16]=source(start_pixel+beat*16+n,burst_epoch);
 end
 always @(posedge clk)begin
  if(!rst_n)begin left<=0;beat<=0;end
  else begin
   if(failed)$fatal(1,"unexpected frame clear fault %h",fault);
   if(frame_valid&&frame_ready)frames=frames+1;
   if(in_valid&&in_ready)admitted=admitted+1;
   if(dut.frame_loading||dut.inner.state==12)begin
    if(in_ready||dut.inner.in_ready||out_valid||frame_ready)$fatal(1,"clear edge admitted or exposed old epoch");
    blocked=blocked+1;
   end
   if(arvalid&&arready)begin
    if(left!=0||arlen!=7||araddr<frame_base)$fatal(1,"DDR ownership during frame clear");
    left<=8;beat<=0;start_pixel<=(araddr-frame_base)*2;burst_epoch<=current_epoch;
   end
   if(left>0&&rvalid)begin left<=left-1;beat<=beat+1;end
   if(out_valid)begin
    if(out_tag!=current_epoch||fx!=13||fy!=37||
       {p00,p10,p01,p11}!={expand(source(0,current_epoch)),expand(source(1,current_epoch)),expand(source(128,current_epoch)),expand(source(129,current_epoch))})
       $fatal(1,"same-base new epoch returned stale pixel/tag");
    outputs=outputs+1;
   end
  end
 end
 task transaction(input integer epoch,base_value,expected_outputs,expected_misses,old_valid);
  integer before_frames,before_inputs;
  begin
   before_frames=frames;before_inputs=admitted;
   @(negedge clk);current_epoch=epoch;frame_base=base_value;in_tag=epoch;in_valid=1;frame_valid=1;
   do @(posedge clk);while(!frame_ready);
   #1;
   if(!dut.frame_loading||dut.frame_loaded||dut.inner.frame_loaded||dut.inner.state!=12||dut.inner.base!=base_value||
      in_ready||dut.inner.in_ready||out_valid||frame_ready)$fatal(1,"accepted frame did not enter blocked loading phase");
   if(old_valid&&dut.inner.valid_lines==0)$fatal(1,"test did not expose physically old valid bits before clear");
   @(negedge clk); // Keep valid high through exactly the blocked CLEAR edge.
   @(posedge clk);#1;
   if(frames!=before_frames+1||admitted!=before_inputs||dut.frame_loading||!dut.frame_loaded||!dut.inner.frame_loaded||
      dut.inner.valid_lines!=0||dut.inner.lru_way!=0||dut.inner.state!=0||dut.inner.base!=base_value)
      $fatal(1,"clear publication, base, or one-clear-edge handshake mismatch");
   clears=clears+1;
   @(negedge clk);frame_valid=0;
   do @(posedge clk);while(!in_ready);
   @(negedge clk);in_valid=0;
   wait(outputs==expected_outputs&&dut.inner.frame_ready);
   repeat(2)@(negedge clk);
   if(misses!=expected_misses)$fatal(1,"new epoch did not refill its two source blocks");
  end
 endtask
 initial begin
  repeat(3)@(negedge clk);rst_n=1;
  transaction(1,0,1,2,0);
  transaction(2,65536,2,4,1);
  transaction(3,65536,3,6,1); // SAME base, different source data epoch.
  @(negedge clk);current_epoch=4;frame_valid=1;
  do @(posedge clk);while(!frame_ready);
  #1;if(!dut.frame_loading||dut.inner.state!=12||in_ready||dut.inner.in_ready||out_valid)$fatal(1,"reset test missed pending clear");
  @(negedge clk);rst_n=0;frame_valid=0;in_valid=0;
  @(posedge clk);#1;
  if(dut.frame_loading||dut.frame_loaded||dut.inner.frame_loaded||dut.inner.valid_lines!=0||dut.inner.lru_way!=0||in_ready||out_valid)
    $fatal(1,"common reset failed to clear loading/valid on its original edge");
  repeat(2)@(negedge clk);rst_n=1;
  transaction(5,65536,4,2,0);
  if(frames!=5||admitted!=4||outputs!=4||clears!=4||blocked!=4)$fatal(1,"vacuous clear epoch/handshake coverage");
  fd=$fopen("frame-clear-public-summary.json","w");
  $fdisplay(fd,"{\"Passed\":true,\"IndexBits\":10,\"FrameTransactions\":5,\"CompletedClearPhases\":4,\"BlockedClearEdges\":4,\"AdmittedQueries\":4,\"IndependentPixelOutputs\":4,\"SameBaseNewEpochRefilled\":true,\"ResetDuringClearSameEdge\":true,\"HeldValidDuringClearNoDoubleAccept\":true,\"StandardReadyValidNotOneShot\":true,\"HierarchyForced\":false}");
  $fclose(fd);$display("PASS FRAME_CLEAR public admission/epoch/reset boundaries");$finish;
 end
 initial begin #300000;$fatal(1,"frame clear public test timeout");end
endmodule
