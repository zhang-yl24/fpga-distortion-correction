`timescale 1ns/1ps
// Preserve the remapper's raster address while tone mapping its RGB565 pixel.
// Geometry mask must be supplied explicitly; real black pixels are samples.
// Both raster and the existing 8x8 tiled order start at tag 0 and end at N-1.
module adaptive_gamma_tagged #(parameter WIDTH=640,HEIGHT=480,TAG_W=24)(
    input clk,rst_n,in_valid,output wire in_ready,
    input [15:0] in_pixel,input [TAG_W-1:0] in_tag,
    input in_masked,auto_enable,
    output wire out_valid,input out_ready,output wire [15:0] out_pixel,
    output reg [TAG_W-1:0] out_tag,output reg out_masked,
    output wire [1:0] out_mode,next_mode,
    output wire [31:0] completed_frames,output wire format_error
);
    wire unused_sof,unused_eof;
    adaptive_gamma_stream #(.WIDTH(WIDTH),.HEIGHT(HEIGHT)) tone(
        .clk(clk),.rst_n(rst_n),.in_valid(in_valid),.in_ready(in_ready),
        .in_pixel(in_pixel),.in_sof(in_tag==0),.in_eof(in_tag==WIDTH*HEIGHT-1),
        .in_masked(in_masked),.auto_enable(auto_enable),
        .out_valid(out_valid),.out_ready(out_ready),.out_pixel(out_pixel),
        .out_sof(unused_sof),.out_eof(unused_eof),.out_mode(out_mode),
        .completed_frames(completed_frames),.format_error(format_error),.next_mode(next_mode)
    );
    always @(posedge clk) begin
        if(!rst_n)begin out_tag<=0;out_masked<=0;end
        else if(in_valid && in_ready)begin out_tag<=in_tag;out_masked<=in_masked;end
    end
endmodule
