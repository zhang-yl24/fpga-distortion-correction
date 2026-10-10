`timescale 1ns/1ps
`include "D:/English/FPGA/distortion/build/cordic_sim/counts.vh"
module tb_cordic_sincos;
    reg clk=0;always #4 clk=~clk;
    reg rst=1,in_valid=0,out_ready=0;reg [31:0] in_phase=0;
    wire in_ready,out_valid;wire signed [31:0] out_cos,out_sin;
    cordic_sincos dut(.*);
    reg [95:0] vectors[0:`CORDIC_N-1];integer n,received=0,ticks=0;
    reg held=0;reg [63:0] hold_data;
    always @(negedge clk) out_ready=!rst && ticks%37>=9;
    always @(posedge clk) begin
        ticks<=ticks+1;
        if(rst) held<=0;
        else begin
            if(held && (!out_valid || {out_cos,out_sin}!==hold_data)) $fatal(1,"CORDIC output changed while stalled");
            held<=out_valid && !out_ready;hold_data<={out_cos,out_sin};
            if(out_valid && out_ready) begin
                if({out_cos,out_sin}!==vectors[received][63:0]) $fatal(1,"CORDIC mismatch %0d got=%h expected=%h",received,{out_cos,out_sin},vectors[received][63:0]);
                received<=received+1;
            end
        end
    end
    task send(input integer index);
        begin
            @(negedge clk);in_valid=1;in_phase=vectors[index][95:64];
            do @(posedge clk);while(!in_ready);
            @(negedge clk);in_valid=0;
        end
    endtask
    initial begin
        $readmemh("vectors.mem",vectors);
        repeat(8) @(negedge clk);rst=0;
        for(n=0;n<`CORDIC_N;n=n+1) send(n);
        wait(received==`CORDIC_N);
        send(0);repeat(7) @(negedge clk);rst=1;repeat(8) @(negedge clk);rst=0;received=0;
        for(n=0;n<16;n=n+1) send(n);
        wait(received==16);
        $display("PASS CORDIC: %0d full-turn independent integer/analytic vectors, quadrant boundaries, output backpressure and mid-computation reset.",`CORDIC_N);$finish;
    end
    initial begin #10000000;$fatal(1,"CORDIC timeout");end
endmodule
