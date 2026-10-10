`timescale 1ns/1ps
module tb_bilinear;
  reg clk=0; always #5 clk=~clk;
  reg rst=1, in_valid=0, out_ready=0;
  wire in_ready,out_valid;
  reg [23:0] p00,p10,p01,p11;
  reg [7:0] fx,fy;
  reg black;
  reg [15:0] tag;
  wire [15:0] out_tag;
  wire [23:0] out_rgb;
  reg [136:0] vectors [0:8191];
  reg [31:0] rng=32'h20261004;
  integer sent=0,received=0,cycles=0,stall_cycles=0;
  integer stalls=0,bubbles=0;
  reg was_stalled=0;
  reg accepted_prev=0;
  reg [23:0] held_rgb;
  reg [15:0] held_tag;
  bilinear_rgb #(.TAG_W(16)) dut(clk,rst,in_valid,in_ready,p00,p10,p01,p11,fx,fy,black,tag,
      out_valid,out_ready,out_rgb,out_tag);
  always @(posedge clk) begin
    if(rst) begin sent=0;received=0;was_stalled=0;accepted_prev=0;end
    else begin
      cycles=cycles+1;
      if(was_stalled && (!out_valid || out_rgb!==held_rgb || out_tag!==held_tag))
        $fatal(1,"Output changed while stalled");
      if(out_valid && out_ready) begin
        if(out_tag!==received[15:0] || out_rgb!==vectors[received][23:0])
          $fatal(1,"Mismatch pixel %0d tag=%0d got=%h expected=%h",received,out_tag,out_rgb,vectors[received][23:0]);
        received=received+1;
      end
      accepted_prev=in_valid && in_ready;
      if(accepted_prev) sent=sent+1;
      was_stalled=out_valid && !out_ready;
      held_rgb=out_rgb;held_tag=out_tag;
      if(was_stalled) stalls=stalls+1;
      if(!in_valid) bubbles=bubbles+1;
      if(cycles>50000) $fatal(1,"Simulation timed out");
    end
  end
  always @(negedge clk) begin
    if(!rst) begin
      rng={rng[30:0],rng[31]^rng[21]^rng[1]^rng[0]};
      // Sustained full-rate traffic, random stalls, and 20-cycle stalls.
      if(cycles%211==0) stall_cycles=20;
      if(stall_cycles>0) begin out_ready=0;stall_cycles=stall_cycles-1;end
      else out_ready=(cycles<100) || rng[3:0]!=0;
      // Advance from the transfer at the preceding edge, not combinational
      // ready after changing the sink control at this edge.
      if(!in_valid || accepted_prev) begin
        in_valid=sent<8192 && ((cycles<100) || rng[7:4]!=0);
        if(sent<8192) begin
          {p00,p10,p01,p11,fx,fy,black}=vectors[sent][136:24];
          tag=sent;
        end
      end
    end
  end
  initial begin
    $readmemh("bilinear.mem",vectors);
    repeat(4) @(negedge clk); rst=0;
    // Reset with data in flight, then restart from vector zero.
    wait(sent>=113); @(negedge clk); rst=1;in_valid=0;out_ready=0;
    repeat(3) @(negedge clk); rst=0;
    wait(received==8192); @(negedge clk);
    $display("PASS bilinear: 8192 pixels, reset in flight, stalls=%0d bubbles=%0d",stalls,bubbles);
    $finish;
  end
endmodule
