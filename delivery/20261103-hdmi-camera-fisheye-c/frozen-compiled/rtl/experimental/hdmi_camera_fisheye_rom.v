`timescale 1ns/1ps
// All ROM operations use the processing clock, including any mapped wide-port
// primitive companion clock. No file reads or independent-domain RAM ports.
module hdmi_camera_fisheye_rom(
    input clk,ce,input [9:0] address,output reg [31:0] base_q30,
    output reg signed [31:0] delta_q30
);
    `include "P:/distortion/work/hdmi-camera-fisheye-20261103-a/build-c/compiled/board/hdmi-camera-fisheye-radial-table.vh"
    always @(posedge clk)if(ce){delta_q30,base_q30}<=fisheye_radial_pair(address);
endmodule
