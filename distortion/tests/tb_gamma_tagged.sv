`timescale 1ns/1ps
module tb_gamma_tagged;
    reg clk=0;always #4 clk=~clk;
    reg rst_n=0,in_valid=0,masked=0,enable=1,out_ready=0;
    reg [15:0] pixel=0;reg [23:0] tag=0;
    wire ready,valid,out_masked,fault;wire [15:0] out_pixel;
    wire [23:0] out_tag;wire [1:0] mode,next_mode;wire [31:0] frames;
    adaptive_gamma_tagged #(.WIDTH(16),.HEIGHT(16)) dut(
        .clk(clk),.rst_n(rst_n),.in_valid(in_valid),.in_ready(ready),.in_pixel(pixel),
        .in_tag(tag),.in_masked(masked),.auto_enable(enable),.out_valid(valid),.out_ready(out_ready),
        .out_pixel(out_pixel),.out_tag(out_tag),.out_masked(out_masked),.out_mode(mode),
        .next_mode(next_mode),.completed_frames(frames),.format_error(fault));
    reg [15:0] golden[0:196607];
    reg [42:0] expected[0:4095],held_data;reg held=0;
    integer pushed=0,popped=0,ticks=0;
    always @(negedge clk)begin ticks=ticks+1;out_ready=(ticks%11>=4);end
    always @(posedge clk)if(rst_n)begin
        if(held && (!valid || {mode,out_masked,out_tag,out_pixel}!==held_data))
            $fatal(1,"Gamma/tag/mask changed during output stall");
        held<=valid && !out_ready;held_data<={mode,out_masked,out_tag,out_pixel};
        if(valid && out_ready)begin
            if(popped>=pushed || {mode,out_masked,out_tag,out_pixel}!==expected[popped])
                $fatal(1,"Gamma tiled tag/pixel/mask mismatch at %0d",popped);
            popped=popped+1;
        end
    end else held<=0;
    task send(input integer address,expected_mode,input [15:0] value,input integer mask);
        begin
            @(negedge clk);pixel=value;tag=address;masked=mask;in_valid=1;
            expected[pushed]={expected_mode[1:0],mask[0],address[23:0],mask?16'd0:golden[expected_mode*65536+value]};
            pushed=pushed+1;
            do @(posedge clk);while(!ready);
            @(negedge clk);in_valid=0;
            if(address%19==7)repeat(3)@(negedge clk);
        end
    endtask
    integer f,i,tx,ty,x,y,m,a;reg [15:0] value;
    initial begin
        $readmemh("golden.mem",golden);repeat(6)@(negedge clk);rst_n=1;
        // Alternate complete raster and 8x8 tile traversal, using the same
        // nonmonotonic raster tags that the live adaptive writer accepts.
        for(f=0;f<10;f=f+1)begin
            case(f)
                0,1:begin value=16'h1082;m=0;end
                2,3:begin value=16'h8410;m=1;end
                4,5:begin value=16'hef7d;m=0;end
                6,7:begin value=16'h0000;m=2;end
                default:begin value=16'h1082;m=0;end
            endcase
            if(f%2==0)begin
                for(i=0;i<256;i=i+1)send(i,m,value,f==6 || f==7 || i%13==8);
            end else begin
                for(ty=0;ty<16;ty=ty+8)for(tx=0;tx<16;tx=tx+8)
                    for(y=0;y<8;y=y+1)for(x=0;x<8;x=x+1)begin
                        a=(ty+y)*16+tx+x;send(a,m,value,f==6 || f==7 || a%13==8);
                    end
            end
        end
        repeat(30)@(negedge clk);
        if(frames!=10 || fault || next_mode!=1 || popped!=2560)
            $fatal(1,"Tagged frame counters/hysteresis/drain incorrect");
        // Real black must participate; explicit geometry mask excludes it.
        for(i=0;i<256;i=i+1)send(i,1,16'h0000,0);
        repeat(30)@(negedge clk);if(frames!=11 || next_mode!=1)$fatal(1,"Real black excluded");
        rst_n=0;repeat(6)@(negedge clk);rst_n=1;pushed=0;popped=0;
        enable=0;for(i=0;i<256;i=i+1)send(i,0,16'h2345,i%7==3);
        repeat(30)@(negedge clk);
        if(frames!=1 || fault || popped!=256)$fatal(1,"Tagged reset/bypass recovery failed");
        $display("PASS tagged Gamma: 12 complete raster/tiled frames, pixel/address/mask atomicity, output stalls, input gaps, two-frame decisions, real-black statistics, explicit mask exclusion, reset and bypass.");$finish;
    end
    initial begin #2000000;$fatal(1,"Tagged Gamma timeout");end
endmodule
