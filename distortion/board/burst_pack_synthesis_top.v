// Device-map harness: the 256-bit packet is an internal DDR/FIFO bus.
// Expose all 16 lanes through a mux instead of allocating 256 package pins.
module burst_pack_synthesis_top(input clk,rst_n,frame_start,line_end,pixel_valid,
    input [15:0] pixel,input beat_ready,input [3:0] lane_select,
    output [15:0] lane_data,output [31:0] beat_byte_offset,dropped_frames,
    output beat_valid,beat_first,beat_last,frame_complete,frame_invalid,overflow_seen);
    wire [255:0] beat_data;
    rgb565_burst_pack pack(.clk(clk),.rst_n(rst_n),.frame_start(frame_start),
        .line_end(line_end),.pixel_valid(pixel_valid),.pixel(pixel),
        .beat_ready(beat_ready),.beat_valid(beat_valid),.beat_data(beat_data),
        .beat_byte_offset(beat_byte_offset),.beat_first(beat_first),.beat_last(beat_last),
        .frame_complete(frame_complete),.frame_invalid(frame_invalid),
        .dropped_frames(dropped_frames),.overflow_seen(overflow_seen));
    assign lane_data=beat_data[lane_select*16 +: 16];
endmodule
