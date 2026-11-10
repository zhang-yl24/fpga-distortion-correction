`timescale 1ns/1ps
// Research-only in-order merge around an unchanged scalar remap core.
// Metadata records every accepted scalar request or independently proved MASK8.
// MASK8 never queries the core; it retires only after every older descriptor.
// Core must return exactly one ordered response for each accepted scalar request.
module ordered_run8_merge #(
 parameter FRAME_PIXELS=2073600,TAG_W=24,DEPTH=2048
)(
 input clk,rst_n,input frame_valid,output frame_ready,
 input token_valid,output token_ready,input [TAG_W-1:0] token_tag,
 input token_black8,token_last,
 output core_in_valid,input core_in_ready,output [TAG_W-1:0] core_in_tag,
 input core_out_valid,output core_out_ready,input [23:0] core_out_rgb,
 input [TAG_W-1:0] core_out_tag,input core_out_masked,
 output out_valid,input out_ready,output [23:0] out_rgb,
 output [TAG_W-1:0] out_tag,output out_masked,out_black8,out_last,
 output reg done,failed,output reg [7:0] fault,
 output reg [31:0] issued_pixels,retired_pixels,scalar_issued,scalar_retired,
 output reg [31:0] issued_tokens,retired_tokens
);
 reg active,issued_end;
 wire q_ready,q_valid,q_empty;
 wire [TAG_W+1:0] q_data;
 wire q_black=q_data[TAG_W],q_last=q_data[TAG_W+1];
 wire [TAG_W-1:0] q_tag=q_data[TAG_W-1:0];
 wire [3:0] token_pixels=token_black8?4'd8:4'd1;
 wire [3:0] head_pixels=q_black?4'd8:4'd1;
 assign frame_ready=!active&&q_empty&&!failed;
 wire frame_fire=frame_valid&&frame_ready;
 wire bad_token=token_tag>=FRAME_PIXELS ||
   ((issued_pixels==0)!=(token_tag==0)) ||
   issued_pixels+token_pixels>FRAME_PIXELS ||
   token_last!=(issued_pixels+token_pixels==FRAME_PIXELS) ||
   (token_last&&(token_tag+(token_black8?7:0)!=FRAME_PIXELS-1)) ||
   (token_black8&&(token_tag[2:0]!=0 || token_tag+7>=FRAME_PIXELS));
 assign token_ready=active&&!issued_end&&!failed&&q_ready&&
   (token_black8||core_in_ready);
 wire issue=token_valid&&token_ready;
 assign core_in_valid=token_valid&&active&&!issued_end&&!failed&&
   !token_black8&&q_ready&&!bad_token;
 assign core_in_tag=token_tag;
 wire tag_mismatch=q_valid&&!q_black&&core_out_valid&&core_out_tag!=q_tag;
 assign out_valid=active&&!failed&&q_valid&&(q_black||core_out_valid)&&!tag_mismatch;
 assign out_tag=q_tag;
 assign out_rgb=q_black?24'd0:core_out_rgb;
 assign out_masked=q_black||core_out_masked;
 assign out_black8=q_black;
 assign out_last=q_last;
 wire retire=out_valid&&out_ready;
 wire unsolicited_response=core_out_valid&&scalar_retired==scalar_issued&&!(issue&&!token_black8&&!bad_token);
 assign core_out_ready=active&&!failed&&q_valid&&!q_black&&out_ready&&!tag_mismatch;
 sync_token_fifo #(.WIDTH(TAG_W+2),.DEPTH(DEPTH)) metadata(
  .clk(clk),.rst_n(rst_n),.clear(frame_fire),
  .in_valid(issue&&!bad_token),.in_ready(q_ready),
  .in_data({token_last,token_black8,token_tag}),
  .out_valid(q_valid),.out_ready(retire),.out_data(q_data),.empty(q_empty));
 initial if(DEPTH<4 || (DEPTH&(DEPTH-1))!=0 || TAG_W<3 ||
   FRAME_PIXELS<8 || FRAME_PIXELS>(64'd1<<TAG_W)) $fatal(1,"invalid merge parameters");
 always @(posedge clk)begin
  if(!rst_n)begin
   active<=0;issued_end<=0;done<=0;failed<=0;fault<=0;
   issued_pixels<=0;retired_pixels<=0;scalar_issued<=0;scalar_retired<=0;
   issued_tokens<=0;retired_tokens<=0;
  end else begin
   done<=0;
   if(frame_fire)begin
    active<=1;issued_end<=0;issued_pixels<=0;retired_pixels<=0;
    scalar_issued<=0;scalar_retired<=0;issued_tokens<=0;retired_tokens<=0;
   end else if(active&&!failed)begin
    if(issue)begin
     if(bad_token)begin failed<=1;fault<=8'h51;end
     else begin
      issued_pixels<=issued_pixels+token_pixels;issued_tokens<=issued_tokens+1;
      if(!token_black8)scalar_issued<=scalar_issued+1;
      if(token_last)issued_end<=1;
     end
    end
    if(tag_mismatch)begin failed<=1;fault<=8'h52;end
    if(unsolicited_response)begin failed<=1;fault<=8'h53;end
    if(retire)begin
     retired_pixels<=retired_pixels+head_pixels;retired_tokens<=retired_tokens+1;
     if(!q_black)scalar_retired<=scalar_retired+1;
     if(q_last)begin
      if(retired_pixels+head_pixels!=FRAME_PIXELS || !issued_end ||
        scalar_retired+(!q_black)!=scalar_issued)begin failed<=1;fault<=8'h54;end
      else begin active<=0;done<=1;end
     end
    end
    // Failure dominates a coincident final token retirement.
    if((issue&&bad_token)||tag_mismatch||unsolicited_response)begin
     failed<=1;done<=0;
     fault<=unsolicited_response?8'h53:tag_mismatch?8'h52:8'h51;
    end
   end
  end
 end
endmodule
