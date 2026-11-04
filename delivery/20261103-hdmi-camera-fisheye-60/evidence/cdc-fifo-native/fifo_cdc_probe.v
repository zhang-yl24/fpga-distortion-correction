module fifo_cdc_probe(
    input wr_clk,rd_clk,rst_n,wr_en,rd_en,input [7:0] wr_data,
    output [7:0] small_data,large_data,output [3:0] ready,
    output [1:0] full,empty,valid,
    output [6:0] small_available,small_used,
    output [9:0] large_available,large_used
);
    video_async_fifo #(.DATA_BITS(8),.ADDR_BITS(6)) capture_size(
        .wr_clk(wr_clk),.rd_clk(rd_clk),.rst_n(rst_n),.wr_en(wr_en),.wr_data(wr_data),
        .rd_en(rd_en),.rd_data(small_data),.rd_valid(valid[0]),.wr_full(full[0]),
        .wr_ready(ready[0]),.rd_empty(empty[0]),.rd_ready(ready[1]),
        .rd_available(small_available),.wr_used(small_used));
    video_async_fifo #(.DATA_BITS(8),.ADDR_BITS(9)) display_size(
        .wr_clk(wr_clk),.rd_clk(rd_clk),.rst_n(rst_n),.wr_en(wr_en),.wr_data(wr_data),
        .rd_en(rd_en),.rd_data(large_data),.rd_valid(valid[1]),.wr_full(full[1]),
        .wr_ready(ready[2]),.rd_empty(empty[1]),.rd_ready(ready[3]),
        .rd_available(large_available),.wr_used(large_used));
endmodule
