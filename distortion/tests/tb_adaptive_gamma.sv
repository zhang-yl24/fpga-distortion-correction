`timescale 1ns/1ps
module tb_adaptive_gamma;
    reg clk=0;always #4 clk=~clk;
    reg rst_n=0,in_valid=0,sof=0,eof=0,masked=0,enable=1;
    reg [15:0] pixel=0;wire ready,valid;reg out_ready=1;
    wire [15:0] out_pixel;wire out_sof,out_eof;wire [1:0] mode,next_mode;
    wire [31:0] frames;wire fault;
    adaptive_gamma_stream #(.WIDTH(8),.HEIGHT(8)) dut(.clk(clk),.rst_n(rst_n),.in_valid(in_valid),.in_ready(ready),.in_pixel(pixel),
        .in_sof(sof),.in_eof(eof),.in_masked(masked),.auto_enable(enable),.out_valid(valid),.out_ready(out_ready),.out_pixel(out_pixel),
        .out_sof(out_sof),.out_eof(out_eof),.out_mode(mode),.completed_frames(frames),.format_error(fault),.next_mode(next_mode));
    reg [15:0] golden[0:196607],expected[0:2047];reg [3:0] tags[0:2047];
    integer pushed=0,popped=0,ticks=0;reg held=0;reg [19:0] held_data;
    always @(negedge clk)begin ticks=ticks+1;out_ready=ticks%7>2;end
    always @(posedge clk)if(rst_n)begin
        if(held && (!valid || {mode,out_sof,out_eof,out_pixel}!==held_data))$fatal(1,"Gamma output changed while stalled");
        held<=valid && !out_ready;held_data<={mode,out_sof,out_eof,out_pixel};
        if(valid && out_ready)begin
            if(popped>=pushed || out_pixel!==expected[popped] || {mode,out_sof,out_eof}!==tags[popped])$fatal(1,"Gamma pixel/mode/frame mismatch at %0d",popped);
            popped=popped+1;
        end
    end else held<=0;
    task send(input [15:0] p,input integer m,input integer start_frame,end_frame,is_masked);
        begin @(negedge clk);pixel=p;sof=start_frame;eof=end_frame;masked=is_masked;in_valid=1;
            expected[pushed]=is_masked ? 0:golden[m*65536+p];tags[pushed]={m[1:0],start_frame[0],end_frame[0]};pushed=pushed+1;
            do @(posedge clk);while(!ready);@(negedge clk);in_valid=0;end
    endtask
    integer i,f,m;reg [15:0] base;
    initial begin
        $readmemh("golden.mem",golden);repeat(8)@(negedge clk);rst_n=1;
        // Two matching complete-frame decisions, never changes inside a frame.
        for(f=0;f<10;f=f+1)begin
            case(f)
                0,1:begin base=16'h1082;m=0;end
                2,3:begin base=16'h8410;m=1;end
                4,5:begin base=16'hef7d;m=0;end
                6,7:begin base=16'h0000;m=2;end
                default:begin base=16'h1082;m=0;end
            endcase
            for(i=0;i<64;i=i+1)send(base,m,i==0,i==63,f==6 || f==7);
        end
        repeat(20)@(negedge clk);
        if(frames!=10 || fault || next_mode!=1)$fatal(1,"Adaptive decision counters incorrect");
        // Disabled frame bypasses all tone changes, even if enable changes mid-frame.
        enable=0;for(i=0;i<64;i=i+1)begin send(16'h2345,0,i==0,i==63,0);if(i==3)enable=1;end
        repeat(20)@(negedge clk);if(popped!=pushed)$fatal(1,"Gamma pipeline did not drain");
        // Malformed/partial frame does not replace the last valid decision.
        send(16'hffff,1,1,0,0);send(16'hffff,1,0,1,0);repeat(20)@(negedge clk);
        if(!fault || frames!=11)$fatal(1,"Malformed frame accepted");
        rst_n=0;repeat(8)@(negedge clk);rst_n=1;pushed=0;popped=0;
        for(i=0;i<64;i=i+1)send(16'h8410,0,i==0,i==63,0);
        repeat(20)@(negedge clk);if(fault || frames!=1 || popped!=64)$fatal(1,"Gamma reset recovery failed");
        $display("PASS adaptive Gamma: ten complete raw-statistic frames, two-frame hysteresis, SOF-locked mode, masked-pixel exclusion, disable locking, held output under stalls, malformed-frame rejection and reset recovery.");$finish;
    end
    initial begin #1000000;$fatal(1,"Adaptive Gamma timeout");end
endmodule
