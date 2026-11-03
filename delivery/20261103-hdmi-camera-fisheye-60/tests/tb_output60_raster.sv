`timescale 1ps/1ps
// Full raster with a one-cycle FIFO return model; no DDR bandwidth model here.
module tb_output60_raster;
 localparam W=1920,H=1080,N=W*H,B=N/16,HT=2200,VT=1125;
 reg clk=0;integer phase=0,half_ps;
 initial forever begin phase=phase+1000000;half_ps=phase/297;phase=phase%297;#(half_ps)clk=~clk;end
 reg rst_n=0;wire req;wire [31:0] epoch;
 reg grant=0,valid=0,bank=0,ack=0;reg [31:0] ge=0,id=0,crc=0;
 wire gack,rd,hs,vs,de,dvalid,dt,dgood,db,fa,ab,fs,fl,pv,failed,draining;
 wire [7:0] r,g,b,fault;wire [31:0] dep,did,dcrc,consumed,aid,frames,under,mismatch;
 reg fv=0;reg [255:0] data=0;
 integer reads=0,version=0,cycles=0,hx=0,hy=0,pixels=0,starts=0,lasts=0;
 integer first_cycle=0;time first_time=0;reg seen=0,previous_done=0;
 wire ready=reads<B && cycles%7>=2;
 ddr_video_output_1080_board dut(
  .clk(clk),.rst_n(rst_n),.enable(1'b1),.abort(1'b0),.abort_fault(8'd0),
  .request_toggle(req),.request_epoch(epoch),.grant_toggle(grant),.grant_valid(valid),
  .grant_epoch(ge),.grant_checksum(crc),.grant_id(id),.grant_bank(bank),.grant_ack_toggle(gack),
  .done_ack_toggle(ack),.fifo_ready(ready),.fifo_valid(fv),.fifo_data(data),.fifo_rd_en(rd),
  .hs(hs),.vs(vs),.de(de),.r(r),.g(g),.b(b),.display_valid(dvalid),
  .done_toggle(dt),.done_good(dgood),.done_epoch(dep),.done_id(did),.done_bank(db),.done_crc(dcrc),
  .consumed_pixels(consumed),.frame_active(fa),.active_id(aid),.active_bank(ab),
  .frame_start(fs),.frame_last(fl),.pixel_valid(pv),.failed(failed),.fault(fault),.draining(draining),
  .completed_frames(frames),.underflows(under),.mismatches(mismatch));
 function automatic [15:0] pattern(input integer i,input integer v);
  pattern=16'h5a3c^(i*73)^(i>>3)^(v*16'h1357);
 endfunction
 function automatic [255:0] word(input integer n,input integer v);
  integer j;begin for(j=0;j<16;j=j+1)word[16*j+:16]=pattern(n*16+j,v);end
 endfunction
 function automatic [23:0] expand(input [15:0] p);
  expand={p[15:11],p[15:13],p[10:5],p[10:9],p[4:0],p[4:2]};
 endfunction
 reg [128:0] snapshot_before,payload_before;
 reg toggle_before,pending_before;
 always @(posedge clk)begin
  fv<=rst_n && rd;
  if(rst_n && rd)begin data<=word(reads,version);reads=reads+1;end
 end
 always @(posedge clk)begin
  cycles=cycles+1;
  if(cycles>6000000)$fatal(1,"raster timeout");
  if(!rst_n || !dut.reset_sync[1])begin hx=0;hy=0;end
  else begin
   if(dut.picture !== (dut.x>=192 && dut.x<2112 && dut.y>=41 && dut.y<1121))
    $fatal(1,"1080p registered picture differs from original raster predicate");
   if(dut.word_end_position_q !== (dut.picture && dut.column[3:0]==15))
    $fatal(1,"1080p registered word-end differs from original raster predicate");
   if(dut.completion_pending && dut.done_pending)$fatal(1,"1080p completion overlapped pending result");
   snapshot_before={dut.lease_epoch,dut.active_id,dut.active_bank,~dut.checksum,dut.pixel_count};
   payload_before={dep,did,db,dcrc,consumed};toggle_before=dt;pending_before=dut.done_pending;
   #1;
   if(pending_before && ({dep,did,db,dcrc,consumed}!==payload_before || dt!==toggle_before))
    $fatal(1,"1080p unacknowledged result changed");
   if(dt!=toggle_before && {dep,did,db,dcrc,consumed}!==snapshot_before)
    $fatal(1,"1080p published snapshot differs from pre-edge full-frame result");
   if(failed)$fatal(1,"scan fault %h",fault);
   if(hs!==(hx<44) || vs!==(hy<5) || de!==(hx>=192 && hx<2112 && hy>=41 && hy<1121))
    $fatal(1,"raster controls differ at x=%0d y=%0d",hx,hy);
   if(pv)begin
    if(!de || {r,g,b}!==expand(pattern(pixels,version)))$fatal(1,"pixel oracle differs %0d",pixels);
    if(fs!==(pixels==0) || fl!==(pixels==N-1))$fatal(1,"frame marker differs");
    if(fs)begin
     starts=starts+1;
     if(starts==1)begin first_cycle=cycles;first_time=$time;end
     else if(cycles-first_cycle!=HT*VT || $time-first_time<64'd16666666665 || $time-first_time>64'd16666666668)
      $fatal(1,"refresh interval differs cycles=%0d ps=%0t",cycles-first_cycle,$time-first_time);
    end
    if(fl)lasts=lasts+1;
    pixels=pixels+1;
   end else if({r,g,b}!==24'd0)$fatal(1,"blanking RGB differs");
   if(hx==HT-1)begin hx=0;hy=hy==VT-1?0:hy+1;end else hx=hx+1;
  end
 end
 initial begin
  repeat(6)@(negedge clk);rst_n=1;
  repeat(2)begin
   wait(req!=seen);@(negedge clk);seen=req;reads=0;pixels=0;
   ge=epoch;id=version+1;bank=version;crc=version==0?32'h1872e3d1:32'h9432f39a;valid=1;grant=!grant;
   wait(dt!=previous_done);@(negedge clk);previous_done=dt;
   if(!dgood || did!=id || db!=bank || dep!=ge || dcrc!=crc || consumed!=N || pixels!=N || reads!=B || under || mismatch)
    $fatal(1,"frame result differs");
   ack=dt;version=version+1;
  end
  if(frames!=2 || starts!=2 || lasts!=2)$fatal(1,"coverage incomplete");
  $display("PASS OUTPUT60 RASTER frames=2 pixels_per_frame=2073600 beats_per_frame=129600 frame_cycles=2475000 refresh_hz=60 crc0=1872e3d1 crc1=9432f39a");
  $finish;
 end
endmodule
