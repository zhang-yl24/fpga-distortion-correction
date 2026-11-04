`timescale 1ns/1ps
// Two PCLK stages, with the same delay for pixels and timing. Normalize all
// eight input bits to the complete 5/6/5 range instead of discarding pad bits.
// For v in [0,255], (t+(t>>8))>>8, t=v*levels+128, equals
// round(v*levels/255), levels=31 or 63. The expanded output is consumed by the
// existing RGB565 capture interface; no change to its DDR word layout is made.
module hdmi_camera_rgb565_quantizer(
    input clk,rst_n,in_valid,in_vs,in_de,
    input [23:0] in_rgb,
    output reg out_valid,out_vs,out_de,
    output [23:0] out_rgb
);
    reg valid0,vs0,de0;
    reg [12:0] r_scale,b_scale;
    reg [13:0] g_scale;
    reg [4:0] r5,b5;
    reg [5:0] g6;
    wire [13:0] r_round={1'b0,r_scale}+{9'b0,r_scale[12:8]};
    wire [13:0] b_round={1'b0,b_scale}+{9'b0,b_scale[12:8]};
    wire [14:0] g_round={1'b0,g_scale}+{9'b0,g_scale[13:8]};
    assign out_rgb={r5,r5[4:2],g6,g6[5:4],b5,b5[4:2]};
    always @(posedge clk)begin
        if(!rst_n)begin
            valid0<=0;vs0<=0;de0<=0;r_scale<=0;g_scale<=0;b_scale<=0;
            out_valid<=0;out_vs<=0;out_de<=0;r5<=0;g6<=0;b5<=0;
        end else begin
            valid0<=in_valid;vs0<=in_valid && in_vs;de0<=in_valid && in_de;
            r_scale<=({in_rgb[23:16],5'b0}-{5'b0,in_rgb[23:16]})+13'd128;
            g_scale<=({in_rgb[15:8],6'b0}-{6'b0,in_rgb[15:8]})+14'd128;
            b_scale<=({in_rgb[7:0],5'b0}-{5'b0,in_rgb[7:0]})+13'd128;
            out_valid<=valid0;out_vs<=valid0 && vs0;out_de<=valid0 && de0;
            r5<=r_round[12:8];g6<=g_round[13:8];b5<=b_round[12:8];
        end
    end
endmodule
