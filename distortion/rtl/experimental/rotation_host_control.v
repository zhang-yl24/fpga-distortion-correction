`timescale 1ns/1ps
// Arbitrary phase command and KEY0 coexist. Only complete CORDIC pairs are
// published; the video engine still locks each pair at a frame boundary.
module rotation_host_control #(
    parameter DEBOUNCE_CYCLES=2500000,LONG_CYCLES=125000000,AUTO_CYCLES=375000000
)(input clk,rst_n,key_n,cmd_valid,output wire cmd_ready,input [7:0] cmd_opcode,
    input [15:0] cmd_seq,input [31:0] cmd_argument,
    output reg auto_mode,cfg_valid,output reg [31:0] cfg_phase,
    output reg signed [31:0] cfg_cos,cfg_sin,
    output reg [15:0] accepted_seq,output reg [31:0] requested_phase,command_count);
    (* async_reg="true" *) reg [1:0] key_sync=3;
    reg stable_key,long_seen,computing;
    reg [31:0] debounce_count,hold_count,auto_count,pending_phase;
    wire cordic_ready,cordic_valid;wire signed [31:0] next_cos,next_sin;
    wire issue=!computing && (!cfg_valid || cfg_phase!=requested_phase);
    assign cmd_ready=rst_n;
    cordic_sincos trig(.clk(clk),.rst(!rst_n),.in_valid(issue),.in_ready(cordic_ready),
        .in_phase(requested_phase),.out_valid(cordic_valid),.out_ready(1'b1),.out_cos(next_cos),.out_sin(next_sin));
    always @(posedge clk or negedge rst_n)
        if(!rst_n)key_sync<=3;else key_sync<={key_sync[0],key_n};
    always @(posedge clk) begin
        if(!rst_n) begin
            stable_key<=1;long_seen<=0;computing<=0;debounce_count<=0;hold_count<=0;auto_count<=0;pending_phase<=0;
            auto_mode<=0;cfg_valid<=0;cfg_phase<=0;cfg_cos<=0;cfg_sin<=0;
            accepted_seq<=0;requested_phase<=0;command_count<=0;
        end else begin
            if(key_sync[1]==stable_key)debounce_count<=0;
            else if(debounce_count>=DEBOUNCE_CYCLES-1)begin
                stable_key<=key_sync[1];debounce_count<=0;
                if(key_sync[1])begin
                    if(!long_seen)requested_phase<=requested_phase+32'h15555555;
                    hold_count<=0;long_seen<=0;auto_count<=0;
                end
            end else debounce_count<=debounce_count+1'b1;
            if(!stable_key && !long_seen && !key_sync[1])begin
                if(hold_count>=LONG_CYCLES-1)begin auto_mode<=!auto_mode;long_seen<=1;auto_count<=0;end
                else hold_count<=hold_count+1'b1;
            end
            if(auto_mode && stable_key && key_sync[1])begin
                if(auto_count>=AUTO_CYCLES-1)begin requested_phase<=requested_phase+32'h15555555;auto_count<=0;end
                else auto_count<=auto_count+1'b1;
            end
            if(issue && cordic_ready)begin computing<=1;pending_phase<=requested_phase;end
            if(cordic_valid)begin
                // Discard obsolete calculations instead of exposing a torn or
                // superseded command when another request arrived in flight.
                if(pending_phase==requested_phase && !(cmd_valid && cmd_ready && cmd_opcode==1 && cmd_argument!=pending_phase))begin cfg_phase<=pending_phase;cfg_cos<=next_cos;cfg_sin<=next_sin;cfg_valid<=1;end
                computing<=0;
            end
            // An accepted host command wins over coincident key/auto events.
            if(cmd_valid && cmd_ready)begin
                accepted_seq<=cmd_seq;command_count<=command_count+1'b1;auto_count<=0;
                if(cmd_opcode==1)begin requested_phase<=cmd_argument;auto_mode<=0;end
                else if(cmd_opcode==2)auto_mode<=cmd_argument[0];
            end
        end
    end
endmodule
