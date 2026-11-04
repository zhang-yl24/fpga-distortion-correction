`timescale 1ns/1ps
// Isolated, backpressured RGB565 tone stage. Raw luminance statistics exclude
// geometry-masked pixels. A decision needs two consistent complete frames and
// changes only at SOF; no claim that tone curves recover clipped information.
module adaptive_gamma_stream #(parameter WIDTH=640,HEIGHT=480)(
    input clk,rst_n,in_valid,output wire in_ready,input [15:0] in_pixel,
    input in_sof,in_eof,in_masked,auto_enable,
    output reg out_valid,input out_ready,output reg [15:0] out_pixel,
    output reg out_sof,out_eof,output reg [1:0] out_mode,
    output reg [31:0] completed_frames,output reg format_error,
    output reg [1:0] next_mode
);
    localparam PIXELS=WIDTH*HEIGHT;
    reg [31:0] pixels,samples,dark,bright;
    reg [1:0] frame_mode,previous_decision;
    reg active,good;
    wire [1:0] selected_mode=in_sof ? (auto_enable ? next_mode:2'd0):frame_mode;
    wire [7:0] r8={in_pixel[15:11],in_pixel[15:13]};
    wire [7:0] g8={in_pixel[10:5],in_pixel[10:9]};
    wire [7:0] b8={in_pixel[4:0],in_pixel[4:2]};
    wire [17:0] weighted=77*r8+150*g8+29*b8;
    wire [7:0] luminance=weighted[15:8];
    wire [31:0] total_samples=(in_sof ? 0:samples)+!in_masked;
    wire [31:0] total_dark=(in_sof ? 0:dark)+(!in_masked && luminance<64);
    wire [31:0] total_bright=(in_sof ? 0:bright)+(!in_masked && luminance>=192);
    wire [1:0] decision=total_samples<PIXELS/4 ? 0:
        total_dark>=(total_samples+1)/2 ? 1:
        total_bright>=(total_samples+1)/2 ? 2:0;
    `include "D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera720-stats-delay/build-c/compiled/rtl/experimental/gamma_curves.vh"
    assign in_ready=rst_n && (!out_valid || out_ready);
    always @(posedge clk)begin
        if(!rst_n)begin
            out_valid<=0;out_pixel<=0;out_sof<=0;out_eof<=0;out_mode<=0;
            completed_frames<=0;format_error<=0;next_mode<=0;frame_mode<=0;
            previous_decision<=0;pixels<=0;samples<=0;dark<=0;bright<=0;active<=0;good<=0;
        end else if(in_ready)begin
            out_valid<=in_valid;
            if(in_valid)begin
                out_pixel<=in_masked ? 16'd0:{gamma5(selected_mode,in_pixel[15:11]),gamma6(selected_mode,in_pixel[10:5]),gamma5(selected_mode,in_pixel[4:0])};
                out_sof<=in_sof;out_eof<=in_eof;out_mode<=selected_mode;
                samples<=total_samples;dark<=total_dark;bright<=total_bright;
                if(in_sof)begin
                    if(active)format_error<=1;
                    active<=1;good<=1;pixels<=1;frame_mode<=selected_mode;
                end else begin
                    pixels<=pixels+1'b1;
                    if(!active || pixels>=PIXELS)begin good<=0;format_error<=1;end
                end
                if(in_eof)begin
                    active<=0;
                    if((in_sof && PIXELS==1) || (!in_sof && active && good && pixels==PIXELS-1))begin
                        completed_frames<=completed_frames+1'b1;
                        if(decision==previous_decision)next_mode<=decision;
                        previous_decision<=decision;
                    end else begin good<=0;format_error<=1;end
                end
            end
        end
    end
endmodule
