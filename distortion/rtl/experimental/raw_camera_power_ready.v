`timescale 1ns/1ps
// Power-on delay with a registered, sticky release signal. COUNT_BITS >= 1.
// Declaration initializers map to FPGA power-up state; there is no external
// reset input. Release occurs on rising edge 2**COUNT_BITS and remains high.
// Downstream clock domains still need their own reset-release synchronizers.
module raw_camera_power_ready #(
    parameter COUNT_BITS = 20
)(
    input clk,
    output reg power_ready = 1'b0
);
    reg [COUNT_BITS-1:0] power_count = {COUNT_BITS{1'b0}};

    always @(posedge clk) begin
        if (!power_ready) begin
            if (&power_count)
                power_ready <= 1'b1;
            else
                power_count <= power_count + 1'b1;
        end
    end
endmodule
