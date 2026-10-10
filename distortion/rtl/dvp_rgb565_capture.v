`timescale 1ns/1ps
// Sensor-local PCLK domain. This is a stream, NOT a clock-domain crossing.
// No backpressure exists on DVP; connect to an async FIFO before the DDR domain.
// Configure VSYNC polarity and byte order only after reading the sensor manual.
module dvp_rgb565_capture #(parameter VSYNC_ACTIVE_HIGH=1, HIGH_BYTE_FIRST=1) (
    input wire pclk, input wire rst,
    input wire vsync, href, input wire [7:0] data,
    output reg pixel_valid, output reg [15:0] pixel,
    output reg frame_start, output reg line_end,
    output reg odd_line_error,
    output reg [31:0] frame_count, output reg [31:0] last_frame_pixels
);
    wire frame_sync = VSYNC_ACTIVE_HIGH ? vsync : !vsync;
    reg sync_prev, href_prev, half;
    reg [7:0] first_byte;
    reg [31:0] pixels;
    reg pixel_carry,frame_carry;
    always @(posedge pclk) begin
        if (rst) begin
            sync_prev <= 0; href_prev <= 0; half <= 0;
            first_byte <= 0; pixel <= 0; pixel_valid <= 0;
            frame_start <= 0; line_end <= 0; odd_line_error <= 0;
            pixels <= 0; frame_count <= 0; last_frame_pixels <= 0;
            pixel_carry<=0;frame_carry<=0;
        end else begin
            sync_prev <= frame_sync; href_prev <= href;
            pixel_valid <= 0; frame_start <= 0; line_end <= 0;
            if (frame_sync && !sync_prev) begin
                frame_start <= 1;
                frame_count[15:0]<=frame_count[15:0]+1'b1;
                if(frame_carry) frame_count[31:16]<=frame_count[31:16]+1'b1;
                frame_carry<=frame_count[15:0]==16'hfffe;
                last_frame_pixels <= pixels; pixels <= 0;
                half <= 0; odd_line_error <= 0;pixel_carry<=0;
            end else if (frame_sync) begin
                half <= 0;
            end else if (href) begin
                if (!half) begin first_byte <= data; half <= 1; end
                else begin
                    pixel <= HIGH_BYTE_FIRST ? {first_byte,data} : {data,first_byte};
                    pixel_valid <= 1;
                    pixels[15:0]<=pixels[15:0]+1'b1;
                    if(pixel_carry) pixels[31:16]<=pixels[31:16]+1'b1;
                    pixel_carry<=pixels[15:0]==16'hfffe;
                    half <= 0;
                end
            end else begin
                half <= 0;
                if (href_prev) begin
                    line_end <= 1;
                    if (half) odd_line_error <= 1;
                end
            end
        end
    end
endmodule
