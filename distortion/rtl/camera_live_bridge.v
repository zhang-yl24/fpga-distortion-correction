`timescale 1ns/1ps
// Acquire exactly one complete sensor frame after arm, retain its validated
// metadata until system reset. The DDR reader consumes a 258-bit async FIFO.
module camera_live_bridge #(parameter WIDTH=640,HEIGHT=480)(
    input cam_clk,ddr_clk,rst_n,arm,
    input vsync,href,input [7:0] data,
    input fifo_rd_en,output [257:0] fifo_data,output fifo_valid,fifo_ready,
    output [9:0] fifo_available,
    output reg source_done,source_valid,output reg [31:0] source_checksum
);
    (* async_reg="true" *) reg [1:0] cam_reset_sync=0,arm_sync=0,done_sync=0;
    reg frozen=0,valid_held=0,done_held=0,started=0;
    reg [31:0] checksum=0,checksum_held=0;
    always @(posedge cam_clk or negedge rst_n)
        if(!rst_n) cam_reset_sync<=0;
        else cam_reset_sync<={cam_reset_sync[0],1'b1};
    wire cap_rst_n=cam_reset_sync[1] && arm_sync[1] && !frozen;
    wire pixel_valid,frame_start,line_end,odd;
    wire [15:0] pixel;
    dvp_rgb565_capture #(.HIGH_BYTE_FIRST(0)) capture(.pclk(cam_clk),.rst(!cap_rst_n),
        .vsync(vsync),.href(href),.data(data),.pixel_valid(pixel_valid),.pixel(pixel),
        .frame_start(frame_start),.line_end(line_end),.odd_line_error(odd),
        .frame_count(),.last_frame_pixels());
    wire beat_valid,beat_ready,beat_first,beat_last,frame_complete,frame_invalid;
    wire [255:0] beat_data;
    rgb565_burst_pack #(.WIDTH(WIDTH),.HEIGHT(HEIGHT)) pack(.clk(cam_clk),.rst_n(cap_rst_n),
        .frame_start(frame_start),.line_end(line_end),.pixel_valid(pixel_valid),.pixel(pixel),
        .beat_valid(beat_valid),.beat_ready(beat_ready),.beat_data(beat_data),
        .beat_byte_offset(),.beat_first(beat_first),.beat_last(beat_last),
        .frame_complete(frame_complete),.frame_invalid(frame_invalid),.dropped_frames(),.overflow_seen());
    `include "D:/English/FPGA/distortion/rtl/video_crc32.vh"
    always @(posedge cam_clk) begin
        if(!cam_reset_sync[1]) begin
            arm_sync<=0;started<=0;frozen<=0;valid_held<=0;done_held<=0;checksum<=0;checksum_held<=0;
        end else begin
            arm_sync<={arm_sync[0],arm};
            if(cap_rst_n && frame_start) started<=1;
            if(beat_valid && beat_ready) checksum<=video_crc32_beat(beat_first ? 32'hFFFFFFFF:checksum,beat_data);
            if(!frozen && cap_rst_n && started && (frame_invalid || (line_end && odd) || frame_complete)) begin
                frozen<=1;done_held<=1;
                valid_held<=frame_complete && !frame_invalid && !odd;
                checksum_held<=~checksum;
            end
        end
    end
    wire full,empty,wr_ready;wire [9:0] wr_used;
    video_async_fifo #(.DATA_BITS(258)) fifo(.wr_clk(cam_clk),.rd_clk(ddr_clk),.rst_n(rst_n),
        .wr_en(beat_valid && beat_ready),.wr_data({beat_first,beat_last,beat_data}),
        .wr_full(full),.wr_ready(wr_ready),.wr_used(wr_used),
        .rd_en(fifo_rd_en),.rd_data(fifo_data),.rd_valid(fifo_valid),
        .rd_empty(empty),.rd_ready(fifo_ready),.rd_available(fifo_available));
    assign beat_ready=wr_ready;
    always @(posedge ddr_clk or negedge rst_n) begin
        if(!rst_n) begin done_sync<=0;source_done<=0;source_valid<=0;source_checksum<=0;end
        else begin
            done_sync<={done_sync[0],done_held};
            if(done_sync[1] && !source_done) begin
                source_done<=1;source_valid<=valid_held;source_checksum<=checksum_held;
            end
        end
    end
endmodule
