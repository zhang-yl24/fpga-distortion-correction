`timescale 1ns/1ps
module tb_dvp;
  reg clk=0;always #5 clk=~clk;
  reg rst=1,vsync=0,href=0;
  reg [7:0] data=0;
  wire valid,frame,line_end,odd;
  wire [15:0] pixel;
  wire [31:0] count,last_pixels;
  integer received=0;
  reg [15:0] expected[0:3];
  dvp_rgb565_capture dut(clk,rst,vsync,href,data,valid,pixel,frame,line_end,odd,count,last_pixels);
  always @(negedge clk) if(!rst && valid) begin
    if(received>=4 || pixel!==expected[received]) $fatal(1,"DVP pixel mismatch index=%0d data=%h",received,pixel);
    received=received+1;
  end
  task sample(input bit v,input bit h,input reg[7:0] d);
    @(negedge clk); #1;vsync=v;href=h;data=d;
  endtask
  initial begin
    expected[0]=16'h1234;expected[1]=16'h5678;expected[2]=16'habcd;expected[3]=16'hef01;
    repeat(3) @(negedge clk);#1;rst=0;
    sample(1,0,0);sample(0,0,0);
    sample(0,1,8'h12);sample(0,1,8'h34);sample(0,1,8'h56);sample(0,1,8'h78);
    sample(0,0,0);sample(0,0,0);
    sample(0,1,8'hab);sample(0,1,8'hcd);sample(0,1,8'hef);sample(0,1,8'h01);
    sample(0,0,0);sample(0,0,0);
    // Truncated byte must not leak into the next line.
    sample(0,1,8'h99);sample(0,0,0);sample(0,0,0);
    if(!odd) $fatal(1,"Missing odd-byte alarm");
    sample(1,0,0);sample(1,0,0);
    if(last_pixels!==4 || count!==2 || received!==4 || odd)
      $fatal(1,"DVP frame counters/reset mismatch");
    $display("PASS DVP: byte order, line boundaries, odd-byte alarm, frame counters");$finish;
  end
  initial begin #10000; $fatal(1,"DVP timeout");end
endmodule
