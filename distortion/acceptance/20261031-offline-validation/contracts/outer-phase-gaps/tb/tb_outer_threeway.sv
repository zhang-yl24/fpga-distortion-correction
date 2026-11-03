`timescale 1ns/1ps
module tb_outer_threeway;
 reg ref_clk=0,pclk=0,ref_run=1,pixel_run=1;
 realtime pixel_half=6.6577895;
 reg reset_n=1,arm_request=0,terminal_request=0;
 reg ready=0,started=0,terminal=0;
 reg [3:0] warmup=0;
 integer x=0,y=0,epoch=0,case_id=0,out;
 reg inject_hs=0,inject_vs=0,compare_enable=0,normal_check=0;
 initial forever begin #18.5185185;if(ref_run)ref_clk=~ref_clk;else ref_clk=0;end
 initial begin #2;forever begin
  wait(pixel_run);#(pixel_half);
  if(pixel_run)begin pclk=1;#(pixel_half);pclk=0;end
 end end
 always @(posedge pclk)begin
  if(x==15)begin x<=0;if(y==7)y<=0;else y<=y+1;end
  else x<=x+1;
 end
 wire de=y<4 && x>=1 && x<=8;
 wire hs=x==12 || (inject_hs && x==10 && y==5);
 wire vs=y==6 || (inject_vs && x==4 && y==2);
 // Source-bound CONTRACT PEER, not the vendor RX or real power-up delay.
 // It is ref registered, asynchronously cleared, has one high interval and
 // waits for a reference initialization prefix. A terminal drop is sticky.
 always @(posedge ref_clk or negedge reset_n)
  if(!reset_n)begin ready<=0;started<=0;terminal<=0;warmup<=0;end
  else begin
   if(warmup!=15)warmup<=warmup+1'b1;
   if(terminal_request)begin ready<=0;terminal<=1;end
   else if(!terminal && !started && warmup==15 && arm_request)begin ready<=1;started<=1;end
  end
 wire [2:0] q,failed,pol,vi,hi,pa,ra,gfailed,tbad,tmeta,ratebad,req,ack,settle,apply,prun,rrun,capture;
 wire [7:0] fault[0:2],gfault[0:2];
 wire [31:0] good[0:2],bad[0:2],edges[0:2];
 wire [15:0] w[0:2],h[0:2];
 wire [104:0] held[0:2],bundle[0:2];
 wire [140:0] public_word[0:2];
 integer apply_count[0:2];
 integer compare_count=0,p_gate_differences=0,r_gate_differences=0,current_public_differences=0;
 reg case_diff_seen=0;
 genvar g;
 generate for(g=0;g<3;g=g+1)begin: routes
  outer_probe #(.KIND(g)) probe(.ref_clk(ref_clk),.pclk(pclk),.reset_n(reset_n),.ready(ready),
   .vs(vs),.hs(hs),.de(de),.qualified(q[g]),.failed(failed[g]),.fault(fault[g]),
   .polarity(pol[g]),.vs_idle(vi[g]),.hs_idle(hi[g]),.good(good[g]),.bad(bad[g]),
   .edges(edges[g]),.width_seen(w[g]),.height_seen(h[g]),.p_active(pa[g]),.r_active(ra[g]),
   .gfailed(gfailed[g]),.tbad(tbad[g]),.tmeta(tmeta[g]),.ratebad(ratebad[g]),.gfault(gfault[g]),
   .request(req[g]),.ack(ack[g]),.settle(settle[g]),.apply(apply[g]),.held(held[g]),
   .ref_bundle(bundle[g]),.prun(prun[g]),.rrun(rrun[g]),.source_capture(capture[g]));
  assign public_word[g]={q[g],failed[g],fault[g],pol[g],vi[g],hi[g],good[g],bad[g],edges[g],w[g],h[g]};
  reg pclean=0,rclean=0;
  integer source_epoch=-1,armed_epoch=-1;
  reg [104:0] armed_bundle,expected_capture;
  reg do_capture;
  reg [7:0] expected_fault;
  initial apply_count[g]=0;
  always @(negedge reset_n)begin pclean=0;rclean=0;source_epoch=-1;armed_epoch=-1;end
  always @(posedge pclk)begin
   if(!prun[g])begin pclean=1;source_epoch=-1;end
   else if(capture[g])begin
    if(!rclean)$fatal(1,"source answers before reference clear case%0d route%0d",case_id,g);
    source_epoch=epoch;
   end
  end
  always @(posedge ref_clk)begin
   do_capture=rrun[g] && settle[g];expected_capture=held[g];
   if(!rrun[g])begin rclean=1;armed_epoch=-1;end
   else begin
    if(do_capture && (!pclean || !rclean || source_epoch!=epoch || armed_epoch!=epoch || held[g]!==armed_bundle))
     $fatal(1,"old epoch or changed bundle at capture case%0d route%0d",case_id,g);
    if(apply[g])begin
     if(!pclean || !rclean || armed_epoch!=epoch)$fatal(1,"old epoch apply route%0d",g);
     apply_count[g]=apply_count[g]+1;
     $fdisplay(out,"APPLY,%0d,%0d,%0d,%0t,%0d,0,0",case_id,g,epoch,$time,good[g]);$fflush(out);
    end
   end
   #0.001;
   if(do_capture && bundle[g]!==expected_capture)$fatal(1,"settle capture value mismatch");
   if(rrun[g] && settle[g] && !do_capture)begin armed_bundle=held[g];armed_epoch=source_epoch;end
   expected_fault=!ra[g]?8'h00:gfailed[g]?gfault[g]:tbad[g]?8'h24:ratebad[g]?8'h25:8'h00;
   if(fault[g]!==expected_fault || failed[g] !== (ra[g] && (gfailed[g] || tbad[g] || ratebad[g])))
    $fatal(1,"fault priority changed case%0d route%0d",case_id,g);
   if(!reset_n || !ready || !ra[g])begin
    if(q[g] || failed[g] || fault[g]!=0 || pol[g])$fatal(1,"invalid public qualification case%0d route%0d",case_id,g);
   end
   if(q[g])begin
    if(!pol[g] || vi[g] || hi[g] || failed[g] || fault[g]!=0 || good[g]<2 || bad[g]!=0 || w[g]!=8 || h[g]!=4 || edges[g]<174 || edges[g]>182)
     $fatal(1,"independent valid-raster oracle rejects route%0d",g);
   end
  end
 end endgenerate
 always @(posedge ref_clk)begin
  #0.002;
  if(pa[0]!==pa[1] || ra[0]!==ra[1])r_gate_differences=r_gate_differences+1;
  if(compare_enable)begin
   compare_count=compare_count+1;
   if(public_word[0]!==public_word[2])$fatal(1,"small candidate public mismatch case=%0d time=%0t base=%h small=%h",case_id,$time,public_word[0],public_word[2]);
   if(public_word[0]!==public_word[1])begin
    current_public_differences=current_public_differences+1;
    if(!case_diff_seen)begin
     case_diff_seen=1;$fdisplay(out,"CURRENT_PUBLIC_DIFF,%0d,1,%0d,%0t,%0d,%0d,%0d",case_id,epoch,$time,good[0],good[1],q[0]!=q[1]);$fflush(out);
    end
   end
   if(normal_check && failed!==0)$fatal(1,"unexpected normal-input fault case%0d",case_id);
  end
 end
 always @(posedge pclk)if(pa[0]!==pa[1])p_gate_differences=p_gate_differences+1;

 task mark(input string label);
  begin
   $display("OUTER_PROGRESS case=%0d epoch=%0d %s",case_id,epoch,label);
   $fdisplay(out,"MARK,%0d,-1,%0d,%0t,%s,0,0",case_id,epoch,$time,label);$fflush(out);
  end
 endtask
 task reset_both;
  begin
   compare_enable=0;normal_check=0;arm_request=0;terminal_request=0;inject_hs=0;inject_vs=0;
   @(negedge ref_clk);epoch=epoch+1;reset_n=0;#1;
   if(q!==0 || failed!==0 || pol!==0 || fault[0]!=0 || fault[1]!=0 || fault[2]!=0)$fatal(1,"common reset did not asynchronously invalidate");
   repeat(3)@(negedge ref_clk);reset_n=1;
   repeat(18)@(negedge ref_clk);compare_enable=1;case_diff_seen=0;
  end
 endtask
 task arm_phase(input integer phase);
  integer tx,ty,n;
  begin
   case(phase)0:begin tx=4;ty=1;end 1:begin tx=15;ty=5;end
    2:begin tx=0;ty=6;end default:begin tx=0;ty=0;end endcase
   n=0;while((x!=tx || y!=ty) && n<512)begin @(negedge pclk);n=n+1;end
   if(n==512)$fatal(1,"raster phase timeout");arm_request=1;
   while(!ready)@(negedge ref_clk);
   $fdisplay(out,"READY,%0d,-1,%0d,%0t,%0d,%0d,%0d",case_id,epoch,$time,x,y,phase);$fflush(out);
  end
 endtask
 task wait_qualified;
  integer n;
  begin
   n=0;normal_check=1;
   while(q!==3'b111 && n<31000)begin @(negedge ref_clk);n=n+1;end
   if(q!==3'b111)$fatal(1,"not all routes qualified case%0d q%h fault%h/%h/%h",case_id,q,fault[0],fault[1],fault[2]);
   repeat(8)@(negedge ref_clk);
   mark("ALL_QUALIFIED");
   $fdisplay(out,"QUALIFIED,%0d,-1,%0d,%0t,%0d,%0d,%0d",case_id,epoch,$time,good[0],good[1],good[2]);$fflush(out);
  end
 endtask
 task terminal_drop;
  begin
   normal_check=0;terminal_request=1;@(negedge ref_clk);
   while(ready)@(negedge ref_clk);
   if(q!==0 || failed!==0 || fault[0]!=0 || fault[1]!=0 || fault[2]!=0)$fatal(1,"terminal drop failed to invalidate");
   repeat(12)@(negedge ref_clk);
   if(q!==0 || good[0]!=0 || good[1]!=0 || good[2]!=0)$fatal(1,"terminal stale publication");
   mark("TERMINAL_INVALID");
  end
 endtask
 integer phase_out;
 realtime ready_stamp=-1,last_de_stamp=-1,last_vs_stamp=-1;
 always @(posedge ready)ready_stamp=$realtime;
 always @(posedge de)last_de_stamp=$realtime;
 always @(posedge vs)last_vs_stamp=$realtime;
 task arm_exact_phase(input integer phase);
  integer ready_x,ready_y;
  realtime delta;
  begin
   // All DUTs are still held invalid. Rephase only the external test raster.
   // Stop the source clock cleanly; allow the generator to reach its wait.
   @(negedge pclk);pixel_run=0;
   repeat(3)@(negedge ref_clk);
   if(ready || pa!==0)$fatal(1,"phase setup occurred after observer activation");
   if(phase==0)begin x=14;y=5;end else begin x=0;y=0;end
   @(negedge ref_clk);arm_request=1;
   // At1ps precision these are the ORIGINAL effective half periods:
   // ref18.519ns, pixel6.658ns. First P posedge and next ref posedge coincide.
   #(18.519-6.658);pixel_run=1;
   @(posedge ready);#0.001;ready_x=x;ready_y=y;
   if(phase==0)begin
    if(x!=15 || y!=5 || vs || de)$fatal(1,"actual ready is not one pixel before VS");
    @(posedge vs);#0.001;delta=last_vs_stamp-ready_stamp;
    if(x!=0 || y!=6 || delta<13.3155 || delta>13.3165)
     $fatal(1,"VS-after-ready edge coverage missing delta=%0.3f",delta);
    $fdisplay(phase_out,"VS_BEFORE,%0d,%0.3f,%0d,%0d,%0.3f,%0d,%0d,%0.3f",case_id,ready_stamp,ready_x,ready_y,last_vs_stamp,x,y,delta);
    mark("ACTUAL_READY_BEFORE_VS");
   end else begin
    delta=last_de_stamp-ready_stamp;
    if(x!=1 || y!=0 || !de || delta < -0.0005 || delta > 0.0005)
     $fatal(1,"actual ready is not same timestamp as first DE edge delta=%0.3f",delta);
    $fdisplay(phase_out,"DE_SAME_EDGE,%0d,%0.3f,%0d,%0d,%0.3f,%0d,%0d,%0.3f",case_id,ready_stamp,ready_x,ready_y,last_de_stamp,x,y,delta);
    mark("ACTUAL_READY_AT_DE_RISE");
   end
   $fflush(phase_out);
  end
 endtask
 integer c,n;
 initial begin
  out=$fopen("outer.csv","w");if(!out)$fatal(1,"open outer.csv");
  $fdisplay(out,"event,case,kind,epoch,time,a,b,c");$fflush(out);
  phase_out=$fopen("phases.csv","w");if(!phase_out)$fatal(1,"open phases.csv");
  $fdisplay(phase_out,"event,case,ready_ns,ready_x,ready_y,edge_ns,edge_x,edge_y,delta_ns");$fflush(phase_out);
  for(c=1;c<=2;c=c+1)begin
   case_id=c;reset_both();arm_exact_phase(c-1);wait_qualified();terminal_drop();
  end
  $fdisplay(phase_out,"PASS,0,0,0,0,0,0,0,0");$fflush(phase_out);$fclose(phase_out);
  if(compare_count<100 || p_gate_differences==0 || r_gate_differences==0)$fatal(1,"comparison coverage vacuous");
  $fdisplay(out,"SUMMARY,0,-1,%0d,%0t,%0d,%0d,%0d",epoch,$time,compare_count,p_gate_differences,r_gate_differences);
  $fdisplay(out,"CURRENT_DIFF_COUNT,0,1,%0d,%0t,%0d,0,0",epoch,$time,current_public_differences);
  $fdisplay(out,"PASS,0,-1,%0d,%0t,THREEWAY_CONTRACT_COMPLETE,0,0",epoch,$time);$fflush(out);$fclose(out);
  $display("OUTER_THREEWAY_CONTRACT_COMPLETE strict_small_public_checks=%0d current_guard_diffs=%0d",compare_count,current_public_differences);$finish;
 end
 initial begin #30000000;$fatal(1,"30ms simulation watchdog");end
endmodule
