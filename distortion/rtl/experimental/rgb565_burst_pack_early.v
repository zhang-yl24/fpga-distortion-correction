`timescale 1ns/1ps
// PCLK-domain adapter: 16 RGB565 pixels per 256-bit DDR/FIFO beat.
// DVP has no backpressure. Overflow invalidates the whole current frame;
// a stalled output is held unchanged, and recovery waits for frame_start.
// WIDTH must be a positive multiple of 16; WIDTH/HEIGHT <= 4095.
// The consumer must publish only after frame_complete AND all DDR writes finish.
module rgb565_burst_pack_early #(parameter WIDTH=640, HEIGHT=480)(
    input clk,rst_n,frame_start,line_end,pixel_valid,
    input [15:0] pixel,
    output reg beat_valid,input beat_ready,
    output reg [255:0] beat_data,
    output reg [31:0] beat_byte_offset,
    output reg beat_first,beat_last,
    output reg frame_complete,frame_invalid,
    output reg [31:0] dropped_frames,
    output reg overflow_seen
);
    reg [255:0] pack;
    reg [3:0] lane;
    reg [11:0] column,row;
    reg [31:0] next_offset;
    reg active,dropping;
    wire output_free=!beat_valid || beat_ready;
    wire size_complete=(row==HEIGHT && column==0 && lane==0);
    always @(posedge clk) begin
        if(!rst_n) begin
            pack<=0;lane<=0;column<=0;row<=0;next_offset<=0;
            active<=0;dropping<=0;beat_valid<=0;beat_data<=0;
            beat_byte_offset<=0;beat_first<=0;beat_last<=0;
            frame_complete<=0;frame_invalid<=0;dropped_frames<=0;overflow_seen<=0;
        end else begin
            frame_complete<=0;frame_invalid<=0;
            if(beat_valid && beat_ready) beat_valid<=0;
            if(frame_start) begin
                frame_complete<=active && !dropping && size_complete && output_free;
                if(active && !dropping && (!size_complete || !output_free)) begin
                    frame_invalid<=1;dropped_frames<=dropped_frames+1'b1;
                end
                pack<=0;lane<=0;column<=0;row<=0;next_offset<=0;active<=1;
                // Never retract an older beat while the receiver is stalled.
                dropping<=!output_free;
                if(!output_free) begin
                    frame_invalid<=1;overflow_seen<=1;
                    dropped_frames<=dropped_frames+1'b1 +
                        (active && !dropping);
                end
            end else if(active && !dropping) begin
                if(line_end) begin
                    if(column!=WIDTH || lane!=0 || row>=HEIGHT || (row==HEIGHT-1 && !output_free)) begin
                        dropping<=1;frame_invalid<=1;dropped_frames<=dropped_frames+1'b1;
                    end else begin
                        row<=row+1'b1;column<=0;
                        // Exact known-height frame, final beat accepted or free.
                        // Pulse after final line end; ignore input until VSYNC.
                        if(row==HEIGHT-1) begin frame_complete<=1;active<=0;end
                    end
                end else if(pixel_valid) begin
                    if(column>=WIDTH || row>=HEIGHT) begin
                        dropping<=1;frame_invalid<=1;dropped_frames<=dropped_frames+1'b1;
                    end else begin
                        column<=column+1'b1;
                        pack[lane*16 +: 16]<=pixel;
                        if(lane==15) begin
                            lane<=0;
                            if(output_free) begin
                                beat_data<={pixel,pack[239:0]};beat_valid<=1;
                                beat_byte_offset<=next_offset;next_offset<=next_offset+32;
                                beat_first<=next_offset==0;
                                beat_last<=column==WIDTH-1 && row==HEIGHT-1;
                            end else begin
                                dropping<=1;frame_invalid<=1;overflow_seen<=1;
                                dropped_frames<=dropped_frames+1'b1;
                            end
                        end else lane<=lane+1'b1;
                    end
                end
            end
        end
    end
endmodule
