`timescale 1ns/1ps
// Demonstration selector in the existing125MHz core domain.
// Three seconds minimum per mode; apply a due change only on a registered
// source commit. The bank already captured the old mode on the preceding
// acceptance edge, so the change belongs to a later complete frame.
module frame_ab_control #(
    parameter integer HOLD_CYCLES=375000000,FIXED_MODE=-1
)(
    input clk,rst_n,commit_pulse,failed,
    output reg correction_enable
);
    localparam integer COUNT_BITS=(HOLD_CYCLES>1)?$clog2(HOLD_CYCLES):1;
    generate if(FIXED_MODE==0 || FIXED_MODE==1)begin: fixed_measurement
        always @(posedge clk or negedge rst_n)begin
            if(!rst_n)correction_enable<=FIXED_MODE==1;
            else if(!failed)correction_enable<=FIXED_MODE==1;
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
