`timescale 1ns/1ps
// Exhaust real counters for legal zero-start, centered, tight and 12-bit-limit
// rasters. No counter force is used; reset and sticky failure do not stop raster.
module output_position_case #(
 parameter ID=0,W=16,H=1,HT=16,VT=3,X0=0,Y0=1,AW=W,AH=H
)(input clk,rst_n,output reg finished=0);
 localparam WX=X0+(AW-W)/2,WY=Y0+(AH-H)/2;
 integer checks=0,frames=0,firsts=0,lasts=0,failed_checks=0;
 reg inject_abort=0;
 wire failed;
 ddr_video_output_1080_board #(.WIDTH(W),.HEIGHT(H),.HT(HT),.VT(VT),
  .HS(0),.VS(0),.X0(X0),.Y0(Y0),.AW(AW),.AH(AH)) dut(
  .clk(clk),.rst_n(rst_n),.enable(1'b0),.abort(inject_abort),.abort_fault(8'hac),
  .grant_toggle(1'b0),.grant_valid(1'b0),.grant_epoch(32'd0),.grant_checksum(32'd0),
  .grant_id(32'd0),.grant_bank(1'b0),.done_ack_toggle(1'b0),
  .fifo_ready(1'b0),.fifo_valid(1'b0),.fifo_data(256'd0),.failed(failed));
 initial if(!dut.CONFIG_OK)$fatal(1,"position case %0d has invalid geometry",ID);
 always @(negedge clk)begin
  if(!rst_n)inject_abort=0;
  else if(checks==HT+3)inject_abort=1;
  else inject_abort=0;
 end
 always @(posedge clk)begin
  if(!rst_n || !dut.reset_sync[1])begin
   checks=0;frames=0;firsts=0;lasts=0;failed_checks=0;finished=0;
  end else if(!finished)begin
   if(dut.picture !== (dut.x>=WX && dut.x<WX+W && dut.y>=WY && dut.y<WY+H))
    $fatal(1,"picture pre-edge mismatch case=%0d x=%0d y=%0d",ID,dut.x,dut.y);
   if(dut.word_end_position_q !== (dut.picture && dut.column[3:0]==15))
    $fatal(1,"word end mismatch case=%0d x=%0d y=%0d",ID,dut.x,dut.y);
   if(dut.x==WX && dut.y==WY)firsts=firsts+1;
   if(dut.x==WX+W-1 && dut.y==WY+H-1)lasts=lasts+1;
   if(dut.x==HT-1 && dut.y==VT-1)frames=frames+1;
   if(failed)failed_checks=failed_checks+1;
   checks=checks+1;
   #1;
   if(dut.picture !== (dut.x>=WX && dut.x<WX+W && dut.y>=WY && dut.y<WY+H))
    $fatal(1,"picture settled mismatch case=%0d x=%0d y=%0d",ID,dut.x,dut.y);
   if(frames==2)begin
    if(firsts!=2 || lasts!=2 || failed_checks==0)$fatal(1,"position coverage missing case=%0d",ID);
    finished=1;
    $display("PASS POSITION CASE id=%0d geometry=%0dx%0d picture=%0dx%0d origin=%0d,%0d checks=%0d firsts=%0d lasts=%0d failed_checks=%0d",ID,HT,VT,W,H,WX,WY,checks,firsts,lasts,failed_checks);
   end
  end
 end
endmodule

module tb_output60_positions;
 reg clk=0,rst_n=0;always #5 clk=~clk;
 wire [5:0] done;
 output_position_case #(.ID(0)) a(clk,rst_n,done[0]);
 output_position_case #(.ID(1),.W(16),.H(2),.HT(17),.VT(3),.X0(1),.Y0(0)) b(clk,rst_n,done[1]);
 output_position_case #(.ID(2),.W(16),.H(3),.HT(37),.VT(9),.X0(2),.Y0(1),.AW(31),.AH(7)) c(clk,rst_n,done[2]);
 output_position_case #(.ID(3),.W(32),.H(4),.HT(40),.VT(6),.X0(8),.Y0(2)) d(clk,rst_n,done[3]);
 output_position_case #(.ID(4),.W(16),.H(1),.HT(4096),.VT(2),.X0(4080),.Y0(0)) e(clk,rst_n,done[4]);
 output_position_case #(.ID(5),.W(16),.H(1),.HT(32),.VT(4096),.X0(0),.Y0(4095)) f(clk,rst_n,done[5]);
 initial begin
  repeat(5)@(negedge clk);rst_n=1;
  repeat(37)@(negedge clk);rst_n=0;
  repeat(3)@(negedge clk);rst_n=1;
  wait(&done);@(negedge clk);
  $display("PASS OUTPUT60 POSITIONS cases=6 reset=mid-raster zero-x zero-y centered tight max-ht4096 max-vt4096");$finish;
 end
 initial begin #4000000;$fatal(1,"position boundary test timeout");end
endmodule
