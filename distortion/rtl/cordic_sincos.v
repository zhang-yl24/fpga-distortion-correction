`timescale 1ns/1ps
// Parameter-rate full-turn CORDIC. Phase is unsigned modulo one turn=2^32.
// Results are signed Q2.30. No DSP or image-coordinate lookup table.
module cordic_sincos(input clk,rst,input in_valid,output in_ready,input [31:0] in_phase,
    output reg out_valid,input out_ready,output reg signed [31:0] out_cos,out_sin);
    `include "D:/English/FPGA/distortion/rtl/cordic-constants.vh"
    reg busy,negate;
    reg [4:0] iteration;
    reg signed [33:0] x,y;
    reg signed [31:0] z;
    wire signed [33:0] shifted_x=x>>>iteration,shifted_y=y>>>iteration;
    wire signed [33:0] next_x=z>=0 ? x-shifted_y:x+shifted_y;
    wire signed [33:0] next_y=z>=0 ? y+shifted_x:y-shifted_x;
    assign in_ready=!rst && !busy && (!out_valid || out_ready);
    always @(posedge clk) begin
        if(rst) begin busy<=0;out_valid<=0;iteration<=0;end
        else begin
            if(out_valid && out_ready) out_valid<=0;
            if(in_valid && in_ready) begin
                x<=34'sd652032874;y<=0;iteration<=0;busy<=1;
                if($signed(in_phase)>32'sh40000000 || $signed(in_phase)< -32'sh40000000) begin
                    z<=in_phase-32'h80000000;negate<=1;
                end else begin z<=in_phase;negate<=0;end
            end else if(busy) begin
                x<=next_x;y<=next_y;
                z<=z>=0 ? z-atan_phase(iteration):z+atan_phase(iteration);
                if(iteration==23) begin
                    out_cos<=negate ? -next_x:next_x;out_sin<=negate ? -next_y:next_y;
                    out_valid<=1;busy<=0;
                end else iteration<=iteration+1'b1;
            end
        end
    end
endmodule
