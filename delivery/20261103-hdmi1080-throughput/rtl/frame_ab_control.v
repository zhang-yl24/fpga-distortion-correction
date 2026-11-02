`timescale 1ns/1ps
// MODE 1: fixed correction for throughput measurement; 0: fixed raw;
// 2: original three-second demonstration. Mode is a build-time parameter.
module frame_ab_control #(
    parameter integer MODE=1,
    parameter integer HOLD_CYCLES=375000000
)(
    input clk,rst_n,commit_pulse,failed,
    output reg correction_enable
);
    localparam integer COUNT_BITS=(HOLD_CYCLES>1)?$clog2(HOLD_CYCLES):1;
    generate if(MODE==0 || MODE==1)begin: fixed_mode
        always @(posedge clk or negedge rst_n)begin
            if(!rst_n)correction_enable<=(MODE==1);
            else correction_enable<=(MODE==1);
        end
    end else if(HOLD_CYCLES<=1)begin: each_frame
        always @(posedge clk or negedge rst_n)begin
            if(!rst_n)correction_enable<=1'b0;
            else if(!failed && commit_pulse)correction_enable<=~correction_enable;
        end
    end else begin: dwell
        reg [COUNT_BITS-1:0] elapsed;
        always @(posedge clk or negedge rst_n)begin
            if(!rst_n)begin elapsed<=0;correction_enable<=1'b0;end
            else if(!failed)begin
                if(elapsed==HOLD_CYCLES-1)begin
                    if(commit_pulse)begin elapsed<=0;correction_enable<=~correction_enable;end
                end else elapsed<=elapsed+1'b1;
            end
        end
    end endgenerate
endmodule
