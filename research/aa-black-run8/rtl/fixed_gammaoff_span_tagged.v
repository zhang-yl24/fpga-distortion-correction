`timescale 1ns/1ps
// Research only: fixed Gamma OFF. No adaptive tone/statistics functionality.
// Tags are raster addresses but may arrive in tiled order. RUN8 tag is its
// first raster address. Ready/valid sources may wait while ready is low.
// Reset is the only abort/fault recovery; partial downstream data must be
// discarded by the frame owner. This module cannot retract consumed pixels.
module fixed_gammaoff_span_tagged #(
    parameter WIDTH=640, HEIGHT=480, TAG_W=24
)(
    input wire clk, rst_n,
    input wire frame_valid, output wire frame_ready,
    input wire in_valid, output wire in_ready,
    input wire [15:0] in_pixel,
    input wire [TAG_W-1:0] in_tag,
    input wire in_masked, in_black_run8,
    output reg out_valid, input wire out_ready,
    output reg [15:0] out_pixel,
    output reg [TAG_W-1:0] out_tag,
    output reg out_masked, out_black_run8,
    output reg [31:0] logical_accepted, accepted_tokens,
    output reg [31:0] completed_frames,
    output reg frame_done, format_error
);
    localparam [63:0] N = 64'd1 * WIDTH * HEIGHT;
    localparam PARAM_OK = WIDTH>0 && HEIGHT>0 && TAG_W>0 && TAG_W<=32 &&
                         N<=64'hffffffff && N<=(64'd1<<TAG_W);
    reg active, input_closed, out_last;
    wire [63:0] span = in_black_run8 ? 64'd8 : 64'd1;
    wire [63:0] tag_end = {{(64-TAG_W){1'b0}},in_tag} + span - 1;
    wire [63:0] next_count = {32'd0,logical_accepted} + span;
    wire at_end = tag_end == N-1;
    wire malformed = tag_end>=N || next_count>N ||
        ((logical_accepted==0) != (in_tag==0)) ||
        (in_black_run8 && (!in_masked || in_pixel!=0 || (in_tag & 7)!=0)) ||
        (at_end != (next_count==N));
    assign frame_ready = rst_n && PARAM_OK && !format_error && !active && !out_valid;
    assign in_ready = rst_n && PARAM_OK && !format_error && active &&
                      !input_closed && (!out_valid || out_ready);
    always @(posedge clk) begin
        if(!rst_n) begin
            active<=0; input_closed<=0; out_valid<=0; out_last<=0;
            out_pixel<=0; out_tag<=0; out_masked<=0; out_black_run8<=0;
            logical_accepted<=0; accepted_tokens<=0; completed_frames<=0;
            frame_done<=0; format_error<=0;
        end else begin
            frame_done<=0;
            if(!PARAM_OK) format_error<=1;
            if(out_valid && out_ready) begin
                out_valid<=0;
                if(out_last && !format_error) begin
                    completed_frames<=completed_frames+1'b1;
                    frame_done<=1; active<=0;
                end
            end
            if(frame_valid && frame_ready) begin
                active<=1; input_closed<=0;
                logical_accepted<=0; accepted_tokens<=0;
            end
            if(in_valid && in_ready) begin
                if(malformed) begin
                    format_error<=1; input_closed<=1;
                end else begin
                    logical_accepted<=next_count[31:0];
                    accepted_tokens<=accepted_tokens+1'b1;
                    out_valid<=1; out_pixel<=in_masked ? 16'd0 : in_pixel;
                    out_tag<=in_tag; out_masked<=in_masked;
                    out_black_run8<=in_black_run8; out_last<=at_end;
                    if(at_end) input_closed<=1;
                end
            end
        end
    end
endmodule
