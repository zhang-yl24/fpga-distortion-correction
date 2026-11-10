`timescale 1ns/1ps
// Research-only fixed AA/Brown macro64x32/tile8 ordinal selector.
// Only the caller can authorize the exact fixed-profile/identity-rotation,
// CORR/GammaOFF snapshot. This module does not inspect geometry or DDR.
// Every accepted output advances exactly 1 or 8 logical pixel positions.
// ROM boundaries deliberately cost a bounded reload bubble; no async ROM read.
module fixed_brown_run8_selector #(
 parameter FRAME_PIXELS=2073600,INTERVALS=266,ROM_FILE="run8_intervals_30bit.mem"
)(
 input clk,rst_n,input frame_valid,output frame_ready,input frame_compress,
 output out_valid,input out_ready,output [20:0] out_ordinal,
 output out_black8,output [3:0] out_pixels,output out_last,
 output reg done,failed,output reg [7:0] fault
);
 (* ram_style="block" *) reg [29:0] rom[0:INTERVALS-1];
 initial $readmemh(ROM_FILE,rom);
 reg active,compress,have_interval,loading,no_more;
 reg [8:0] interval_index;
 reg [20:0] ordinal;
 reg [29:0] rom_q;
 reg [17:0] first_run;
 reg [18:0] end_run;
 wire start=frame_valid&&frame_ready;
 wire read_interval=start&&frame_compress || active&&compress&&!have_interval&&!loading&&!no_more;
 wire [8:0] read_index=start ? 9'd0:interval_index;
 always @(posedge clk)if(rst_n&&read_interval)rom_q<=rom[read_index];
 wire [18:0] current_run={1'b0,ordinal[20:3]};
 assign frame_ready=!active&&!failed;
 assign out_valid=active&&!failed&&(!compress||have_interval||no_more);
 assign out_ordinal=ordinal;
 assign out_black8=compress&&have_interval&&ordinal[2:0]==0&&current_run>=first_run&&current_run<end_run;
 assign out_pixels=out_black8?4'd8:4'd1;
 assign out_last=ordinal+out_pixels==FRAME_PIXELS;
 wire fire=out_valid&&out_ready;
 always @(posedge clk)begin
  if(!rst_n)begin
   active<=0;compress<=0;have_interval<=0;loading<=0;no_more<=0;interval_index<=0;ordinal<=0;first_run<=0;end_run<=0;done<=0;failed<=0;fault<=0;
  end else begin
   done<=0;
   if(start)begin
    if(FRAME_PIXELS!=2073600||INTERVALS!=266)begin failed<=1;fault<=8'h40;end
    else begin
     active<=1;compress<=frame_compress;have_interval<=0;loading<=frame_compress;no_more<=0;interval_index<=0;ordinal<=0;
    end
   end else if(active&&!failed)begin
    if(read_interval)loading<=1;
    if(loading)begin
     loading<=0;have_interval<=1;
     first_run<=rom_q[17:0];end_run<={1'b0,rom_q[17:0]}+rom_q[29:18];
     if(rom_q[29:18]==0 || ({1'b0,rom_q[17:0]}+rom_q[29:18])>FRAME_PIXELS/8 || {1'b0,rom_q[17:0]}<current_run)begin have_interval<=0;failed<=1;fault<=8'h41;end
    end
    if(fire)begin
     if(ordinal+out_pixels>FRAME_PIXELS || (compress&&have_interval&&current_run>end_run))begin failed<=1;fault<=8'h42;end
     else if(out_last)begin active<=0;done<=1;end
     else begin
      ordinal<=ordinal+out_pixels;
      if(out_black8&&current_run+1'b1==end_run)begin
       have_interval<=0;
       if(interval_index==INTERVALS-1)no_more<=1;
       else interval_index<=interval_index+1'b1;
      end
     end
    end
   end
  end
 end
endmodule
