`timescale 1ns/1ps
module tb_engine_fifo_a;
 reg clk=0,rst_n=0;
 always #4 clk=~clk;
 wire frame_ready,failed;
 hdmi_camera_fisheye_engine_tile8 #(.WIDTH(16),.HEIGHT(16)) dut(
 .clk(clk),.rst_n(rst_n),.frame_valid(1'b0),.frame_ready(frame_ready),.cfg_corrected(1'b1),
 .source_base(28'd0),.output_base(28'h200000),.frame_id(32'd1),.arready(1'b0),
 .rdata(256'd0),.rvalid(1'b0),.rlast(1'b0),.rid(4'd0),.awready(1'b0),.wready(1'b0),.failed(failed));
 reg [47:0] expected[0:8191];
 integer head=0,tail=0,pushes=0,pops=0,canceled=0,fullpop=0,both=0,masked=0;
 integer resets_queued=0,faults_queued=0,maxcount=0,cycle_id=0,warmfirst=-1,warmlast=-1,warmoutputs=0;
 integer serial=0,i,j,fd;
 reg held=0,warm=0;
 reg [31:0] rng=32'h51c04bad;
 always @(posedge clk)begin
   cycle_id=cycle_id+1;
   if(!rst_n || failed)begin
     if(tail>head)begin
       if(!rst_n)resets_queued=resets_queued+1;else faults_queued=faults_queued+1;
       canceled=canceled+tail-head;
     end
     head=tail;held=0;
   end else begin
     if(dut.buffer_count>2)$fatal(1,"FIFO count exceeds capacity");
     if(dut.buffer_count!=tail-head)$fatal(1,"independent occupancy mismatch");
     if(dut.buffer_count>maxcount)maxcount=dut.buffer_count;
     if(dut.buffer_count==2 && dut.writer_input_ready)begin
       if(dut.result_ready)$fatal(1,"full+pop must not use lookahead ready");
       fullpop=fullpop+1;
     end
     if(dut.buffer_pop)begin
       if(head>=tail)$fatal(1,"writer consumed empty queue");
       if({dut.buffer_tag,dut.buffer_rgb}!==expected[head])$fatal(1,"RGB/mask/tag order differs");
       $fdisplay(fd,"O %06x %06x",dut.buffer_tag,dut.buffer_rgb);
       head=head+1;pops=pops+1;
       if(warm)begin
         if(warmfirst<0)warmfirst=cycle_id;
         warmlast=cycle_id;warmoutputs=warmoutputs+1;
       end
     end
     if(dut.buffer_push)begin
       expected[tail]={dut.result_tag,dut.result_masked ? 24'd0:dut.result_rgb};
       $fdisplay(fd,"I %06x %06x %0d",dut.result_tag,dut.result_rgb,dut.result_masked);
       tail=tail+1;pushes=pushes+1;if(dut.result_masked)masked=masked+1;
     end
     if(dut.buffer_push&&dut.buffer_pop)both=both+1;
     held=dut.result_valid&&!dut.result_ready;
   end
 end
 task tick(input integer offer,input integer ready,input integer mask);
   reg saved_ready;
   begin
    @(negedge clk);
    if(!held)begin
      dut.core.test_valid=offer;
      case(serial%4)
       0:dut.core.test_rgb=24'hff005a;
       1:dut.core.test_rgb=24'h00ffaa;
       2:dut.core.test_rgb=24'ha5813c;
       3:dut.core.test_rgb=24'h123456;
      endcase
      dut.core.test_tag=serial;dut.core.test_masked=mask;serial=serial+1;
    end
    saved_ready=dut.result_ready;dut.writer.test_ready=ready;
    #1;if(dut.result_ready!==saved_ready)$fatal(1,"admission ready depends on writer ready");
    @(posedge clk);#1;
   end
 endtask
 task drain;
   begin
    while(held)tick(0,1,0);
    tick(0,1,0);
    while(dut.buffer_count!=0)tick(0,1,0);
    if(!frame_ready)$fatal(1,"frame cannot restart after exact queue drain");
   end
 endtask
 initial begin
   fd=$fopen("fifo-events.txt","w");
   repeat(3)@(posedge clk);@(negedge clk);rst_n=1;
   // 64 consecutive whole-pixel outputs at one per cycle.
   warm=1;
   for(i=0;i<64;i=i+1)tick(1,1,i%3==0);
   tick(0,1,0);warm=0;
   if(warmoutputs!=64 || warmlast-warmfirst!=63)$fatal(1,"warm II1 failed");
   // Full queue, then simultaneous full+pop with no ready lookahead.
   tick(1,0,0);tick(1,0,1);tick(1,0,0);tick(1,1,0);drain();
   for(i=0;i<1200;i=i+1)begin
     rng={rng[30:0],rng[31]^rng[21]^rng[1]^rng[0]};
     tick(rng[0]|rng[5],rng[2]|rng[7],rng[9]);
   end
   drain();
   // Reset with both entries occupied; no canceled pixel reaches writer.
   tick(1,0,0);tick(1,0,1);
   @(negedge clk);rst_n=0;dut.core.test_valid=0;dut.writer.test_ready=0;
   repeat(2)@(posedge clk);@(negedge clk);rst_n=1;
   tick(1,1,0);drain();
   // Sticky real engine failure flushes the occupied whole-pixel queue.
   tick(1,0,0);tick(1,0,1);
   @(negedge clk);dut.core.test_failed=1;
   repeat(3)@(posedge clk);#1;
   if(!failed||dut.buffer_count!=0||dut.writer.in_valid)$fatal(1,"failed engine did not flush/quarantine queue");
   @(negedge clk);rst_n=0;dut.core.test_failed=0;dut.core.test_valid=0;
   repeat(2)@(posedge clk);@(negedge clk);rst_n=1;
   tick(1,1,1);drain();
   if(!(pushes>500&&pops>500&&fullpop>0&&both>300&&masked>0&&resets_queued>0&&faults_queued>0&&maxcount==2))$fatal(1,"vacuous FIFO coverage");
   if(pushes!=pops+canceled || tail!=head)$fatal(1,"final exact drain/accounting failed");
   $fclose(fd);
   $display("PASS ENGINE_FIFO pushes%0d pops%0d canceled%0d fullpop%0d both%0d masked%0d reset%0d fault%0d warm%0d/%0d max%0d",pushes,pops,canceled,fullpop,both,masked,resets_queued,faults_queued,warmoutputs,warmlast-warmfirst,maxcount);
   $finish;
 end
 initial begin #100000;$fatal(1,"bounded FIFO test timeout");end
endmodule

module hdmi_camera_fisheye_core #(parameter WIDTH=1920,HEIGHT=1080,INDEX_BITS=10,TIMEOUT_BITS=26)(
 input clk,rst_n,frame_valid,output frame_ready,input [27:0] frame_base,input cfg_corrected,
 input in_valid,output in_ready,input signed [23:0] in_u,in_v,input [23:0] in_tag,
 output out_valid,input out_ready,output [23:0] out_rgb,out_tag,output out_masked,
 output [27:0] araddr,output [3:0] arlen,output arvalid,input arready,input [255:0] rdata,
 input rvalid,rlast,input [3:0] rid,output failed,output [7:0] fault,output [31:0] hits,misses,completed_queries);
 reg test_valid=0,test_masked=0,test_failed=0;reg [23:0] test_rgb=0,test_tag=0;
 assign frame_ready=1;assign in_ready=1;assign out_valid=test_valid;assign out_rgb=test_rgb;assign out_tag=test_tag;
 assign out_masked=test_masked;assign failed=test_failed;assign fault=8'h41;
 assign araddr=0;assign arlen=0;assign arvalid=0;assign hits=0;assign misses=0;assign completed_queries=0;
endmodule
module ddr_adaptive_result_writer_dualstripe #(parameter WIDTH=1920,HEIGHT=1080,TIMEOUT_BITS=26)(
 input clk,rst_n,frame_valid,output frame_ready,input [27:0] frame_base,input [31:0] frame_id,input frame_tiled,
 input in_valid,output in_ready,input [23:0] in_rgb,in_tag,output [27:0] awaddr,output [3:0] awlen,
 output awvalid,input awready,output [255:0] wdata,output [31:0] wstrb,input wready,output wlast,
 output done,failed,output [7:0] fault,output [31:0] accepted_pixels,written_beats,last_checksum,completed_id);
 reg test_ready=0;
 assign frame_ready=1;assign in_ready=test_ready;assign awaddr=0;assign awlen=0;assign awvalid=0;
 assign wdata=0;assign wstrb=0;assign wlast=0;assign done=0;assign failed=0;assign fault=0;
 assign accepted_pixels=0;assign written_beats=0;assign last_checksum=0;assign completed_id=0;
endmodule
