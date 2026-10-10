`timescale 1ns/1ps
// KEY0 short press advances 30 degrees; long press toggles a slow auto_mode
// twelve-angle demonstration. Parameter pairs are committed atomically after
// CORDIC completes; consumers must accept them at their own frame boundary.
module rotation_demo_control #(
    parameter DEBOUNCE_CYCLES=2500000,LONG_CYCLES=125000000,AUTO_CYCLES=375000000
)(input clk,rst_n,key_n, output reg auto_mode,
    output reg cfg_valid,output reg [31:0] cfg_phase,
    output reg signed [31:0] cfg_cos,cfg_sin);
    (* async_reg="true" *) reg [1:0] key_sync=3;
    reg stable_key;reg [31:0] debounce_count,hold_count,auto_count;
    reg long_seen;reg [3:0] desired_index,pending_index;
    reg computing;
    wire cordic_ready,cordic_valid;
    wire signed [31:0] next_cos,next_sin;
    function [31:0] phase_for(input [3:0] index);
        case(index)
            0:phase_for=32'h00000000;1:phase_for=32'h15555555;
            2:phase_for=32'h2AAAAAAB;3:phase_for=32'h40000000;
            4:phase_for=32'h55555555;5:phase_for=32'h6AAAAAAB;
            6:phase_for=32'h80000000;7:phase_for=32'h95555555;
            8:phase_for=32'hAAAAAAAB;9:phase_for=32'hC0000000;
            10:phase_for=32'hD5555555;default:phase_for=32'hEAAAAAAB;
        endcase
    endfunction
    wire issue=!computing && (!cfg_valid || cfg_phase!=phase_for(desired_index));
    cordic_sincos trig(.clk(clk),.rst(!rst_n),.in_valid(issue),.in_ready(cordic_ready),
        .in_phase(phase_for(desired_index)),.out_valid(cordic_valid),.out_ready(1'b1),
        .out_cos(next_cos),.out_sin(next_sin));
    always @(posedge clk or negedge rst_n)
        if(!rst_n) key_sync<=3;else key_sync<={key_sync[0],key_n};
    always @(posedge clk) begin
        if(!rst_n) begin
            stable_key<=1;debounce_count<=0;hold_count<=0;auto_count<=0;
            long_seen<=0;desired_index<=0;pending_index<=0;computing<=0;
            auto_mode<=0;cfg_valid<=0;cfg_phase<=0;cfg_cos<=0;cfg_sin<=0;
        end else begin
            if(key_sync[1]==stable_key) debounce_count<=0;
            else if(debounce_count>=DEBOUNCE_CYCLES-1) begin
                stable_key<=key_sync[1];debounce_count<=0;
                if(key_sync[1]) begin
                    if(!long_seen) desired_index<=desired_index==11 ? 0:desired_index+1'b1;
                    hold_count<=0;long_seen<=0;auto_count<=0;
                end
            end else debounce_count<=debounce_count+1'b1;
            // Do not overwrite the release branch's hold-counter reset.
            // Counting a synchronized release here would accumulate short
            // presses and eventually misclassify one as a long press.
            if(!stable_key && !long_seen && !key_sync[1]) begin
                if(hold_count>=LONG_CYCLES-1) begin
                    auto_mode<=!auto_mode;long_seen<=1;auto_count<=0;
                end else hold_count<=hold_count+1'b1;
            end
            if(auto_mode && stable_key && key_sync[1]) begin
                if(auto_count>=AUTO_CYCLES-1) begin
                    desired_index<=desired_index==11 ? 0:desired_index+1'b1;auto_count<=0;
                end else auto_count<=auto_count+1'b1;
            end
            if(issue && cordic_ready) begin computing<=1;pending_index<=desired_index;end
            if(cordic_valid) begin
                cfg_phase<=phase_for(pending_index);cfg_cos<=next_cos;cfg_sin<=next_sin;
                cfg_valid<=1;computing<=0;
            end
        end
    end
endmodule
