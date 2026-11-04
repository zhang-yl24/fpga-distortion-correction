`timescale 1ns/1ps
// Development frame selector, entirely in the existing core clock domain.
// rst_n is the board's existing async-assert/sync-release core_reset[1].
// The bank snapshots correction_enable on its actual source handshake.
// System source_commit is registered by that handshake: this controller sees
// it at the NEXT posedge and toggles only the configuration for a later frame.
// A sticky failure holds configuration while the existing datapath drains.
module frame_ab_control_reference(
    input clk,rst_n,commit_pulse,failed,
    output reg correction_enable
);
    always @(posedge clk or negedge rst_n) begin
        if(!rst_n) correction_enable<=1'b0;
        else if(!failed && commit_pulse) correction_enable<=~correction_enable;
    end
endmodule
