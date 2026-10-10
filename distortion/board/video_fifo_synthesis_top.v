// Narrow synthesis harness. Eight independently loadable lanes keep the full
// 256-bit memory meaningful while staying within physical package IO limits.
module video_fifo_synthesis_top(
    input wr_clk,rd_clk,rst_n,wr_en,rd_en,load,
    input [2:0] input_lane,output_lane,
    input [31:0] word,
    output [31:0] read_word,
    output wr_full,wr_ready,rd_empty,rd_ready,rd_valid,
    output [9:0] wr_used,rd_available
);
    reg [255:0] buffer;
    always @(posedge wr_clk) if(load) buffer[input_lane*32+:32]<=word;
    wire [255:0] rd_data;
    video_async_fifo fifo(.wr_clk(wr_clk),.rd_clk(rd_clk),.rst_n(rst_n),
        .wr_en(wr_en),.wr_data(buffer),.wr_full(wr_full),.wr_ready(wr_ready),
        .rd_en(rd_en),.rd_data(rd_data),.rd_valid(rd_valid),.rd_empty(rd_empty),
        .rd_ready(rd_ready),.wr_used(wr_used),.rd_available(rd_available));
    assign read_word=rd_data[output_lane*32+:32];
endmodule
