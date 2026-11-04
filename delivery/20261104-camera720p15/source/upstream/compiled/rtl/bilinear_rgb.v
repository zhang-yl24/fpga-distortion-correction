`timescale 1ns/1ps
// Four RGB888 neighbours, Q0.8 fractions, rounded once after both axes.
// Shared pipeline enable preserves pixels and tags under downstream stalls.
module bilinear_rgb #(parameter TAG_W = 24) (
    input wire clk, input wire rst,
    input wire in_valid, output wire in_ready,
    input wire [23:0] p00, p10, p01, p11,
    input wire [7:0] fx, fy,
    input wire black, input wire [TAG_W-1:0] in_tag,
    output wire out_valid, input wire out_ready,
    output wire [23:0] out_rgb, output wire [TAG_W-1:0] out_tag
);
    reg [2:0] valid;
    reg [16:0] h0 [0:2];
    reg [16:0] h1 [0:2];
    reg [25:0] vertical [0:2];
    reg [7:0] fy0;
    reg black0, black1;
    reg [TAG_W-1:0] tag0, tag1, tag2;
    reg [23:0] rgb2;
    wire advance = !valid[2] || out_ready;
    wire [8:0] wx0 = 9'd256 - {1'b0, fx};
    wire [8:0] wy0 = 9'd256 - {1'b0, fy0};
    integer c;
    assign in_ready = !rst && advance;
    assign out_valid = valid[2];
    assign out_rgb = rgb2;
    assign out_tag = tag2;
    always @(posedge clk) begin
        if (rst) begin
            valid <= 0;
            fy0 <= 0;
            black0 <= 0; black1 <= 0;
            tag0 <= 0; tag1 <= 0; tag2 <= 0; rgb2 <= 0;
            for (c=0; c<3; c=c+1) begin
                h0[c] <= 0; h1[c] <= 0; vertical[c] <= 0;
            end
        end else if (advance) begin
            valid <= {valid[1:0], in_valid};
            fy0 <= fy; black0 <= black; black1 <= black0;
            tag0 <= in_tag; tag1 <= tag0; tag2 <= tag1;
            for (c=0; c<3; c=c+1) begin
                h0[c] <= p00[8*c +: 8]*wx0 + p10[8*c +: 8]*{1'b0,fx};
                h1[c] <= p01[8*c +: 8]*wx0 + p11[8*c +: 8]*{1'b0,fx};
                vertical[c] <= h0[c]*wy0 + h1[c]*{1'b0,fy0} + 26'd32768;
                rgb2[8*c +: 8] <= black1 ? 8'd0 : vertical[c][23:16];
            end
        end
    end
endmodule
