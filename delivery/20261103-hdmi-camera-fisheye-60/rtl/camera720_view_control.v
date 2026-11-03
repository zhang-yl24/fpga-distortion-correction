`timescale 1ns/1ps
// KEY1: active low, synchronized and debounced in the 125 MHz core domain.
// This is a requested view only. The mapper latches the selected parameters
// on its existing frame handshake, so a button press cannot split a frame.
module camera720_view_control #(
    parameter integer DEBOUNCE_CYCLES=2500000 // 20 ms at 125 MHz; >= 1
)(
    input clk,rst_n,key1_n,
    output reg corrected_requested,
    output reg toggle_pulse
);
    localparam integer COUNT_WIDTH=(DEBOUNCE_CYCLES>1) ? $clog2(DEBOUNCE_CYCLES):1;
    localparam [COUNT_WIDTH-1:0] LAST_COUNT=DEBOUNCE_CYCLES-1;
    // Reset to pressed: even DEBOUNCE_CYCLES=1 must observe a real release
    // through both synchronizer stages before a held-at-reset key can trigger.
    (* PAP_ASYNC_REG=1, syn_srlstyle="registers" *) reg [1:0] key_sync=0;
    reg armed;
    reg [COUNT_WIDTH-1:0] stable_count;
    always @(posedge clk) begin
        if(!rst_n) begin
            key_sync<=0;
            armed<=0;
            stable_count<=0;
            corrected_requested<=1;
            toggle_pulse<=0;
        end else begin
            key_sync<={key_sync[0],key1_n};
            toggle_pulse<=0;
            // While disarmed, count a continuous release. While armed,
            // count a continuous press. Every opposite sample restarts it.
            if(key_sync[1]==!armed) begin
                if(stable_count==LAST_COUNT) begin
                    stable_count<=0;
                    armed<=!armed;
                    if(armed) begin
                        corrected_requested<=!corrected_requested;
                        toggle_pulse<=1;
                    end
                end else stable_count<=stable_count+1'b1;
            end else stable_count<=0;
        end
    end
endmodule
