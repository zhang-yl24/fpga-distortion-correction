`timescale 1ns/1ps
// Dual-clock, synchronous-read queue. Depth=2**ADDR_BITS; ADDR_BITS>=2.
// Both domains must share an asynchronously asserted reset and synchronize its
// release locally. Do not reset only one side while the other continues.
// rd_data is valid one read-clock cycle after an accepted rd_en.
// Gray pointer CDC requires a physical max-delay/bus-skew bound of at most
// one source clock period when integrating into a routed board build.
module video_async_fifo #(parameter DATA_BITS=256,ADDR_BITS=9)(
    input wr_clk,rd_clk,rst_n,
    input wr_en,input [DATA_BITS-1:0] wr_data,
    output wire wr_full,wr_ready,
    input rd_en,
    output reg [DATA_BITS-1:0] rd_data,
    output reg rd_valid,
    output wire rd_empty,rd_ready,
    output wire [ADDR_BITS:0] rd_available,
    output wire [ADDR_BITS:0] wr_used
);
    localparam PTR_BITS=ADDR_BITS+1;
    reg [DATA_BITS-1:0] memory[0:(1<<ADDR_BITS)-1];
    (* async_reg="true" *) reg [1:0] wr_reset_sync=0,rd_reset_sync=0;
    always @(posedge wr_clk or negedge rst_n)
        if(!rst_n) wr_reset_sync<=0;
        else wr_reset_sync<={wr_reset_sync[0],1'b1};
    always @(posedge rd_clk or negedge rst_n)
        if(!rst_n) rd_reset_sync<=0;
        else rd_reset_sync<={rd_reset_sync[0],1'b1};
    reg [PTR_BITS-1:0] wr_binary=0,rd_binary=0,wr_gray=0,rd_gray=0;
    (* async_reg="true" *) reg [PTR_BITS-1:0] rd_gray_w1=0,rd_gray_w2=0;
    (* async_reg="true" *) reg [PTR_BITS-1:0] wr_gray_r1=0,wr_gray_r2=0;
    assign wr_full=wr_gray=={~rd_gray_w2[PTR_BITS-1:PTR_BITS-2],rd_gray_w2[PTR_BITS-3:0]};
    assign rd_empty=rd_gray==wr_gray_r2;
    assign wr_ready=wr_reset_sync[1] && !wr_full;
    assign rd_ready=rd_reset_sync[1] && !rd_empty;
    function [PTR_BITS-1:0] gray_to_binary;
        input [PTR_BITS-1:0] gray;
        integer bit_index;
        begin
            gray_to_binary[PTR_BITS-1]=gray[PTR_BITS-1];
            for(bit_index=PTR_BITS-2;bit_index>=0;bit_index=bit_index-1)
                gray_to_binary[bit_index]=gray_to_binary[bit_index+1]^gray[bit_index];
        end
    endfunction
    assign rd_available=gray_to_binary(wr_gray_r2)-rd_binary;
    assign wr_used=wr_binary-gray_to_binary(rd_gray_w2);
    wire [PTR_BITS-1:0] next_wr=wr_binary+1'b1,next_rd=rd_binary+1'b1;
    always @(posedge wr_clk) begin
        if(!wr_reset_sync[1]) begin wr_binary<=0;wr_gray<=0;rd_gray_w1<=0;rd_gray_w2<=0;end
        else begin
            rd_gray_w1<=rd_gray;rd_gray_w2<=rd_gray_w1;
            if(wr_en && wr_ready) begin
                memory[wr_binary[ADDR_BITS-1:0]]<=wr_data;
                wr_binary<=next_wr;wr_gray<=(next_wr>>1)^next_wr;
            end
        end
    end
    always @(posedge rd_clk) begin
        if(!rd_reset_sync[1]) begin
            rd_binary<=0;rd_gray<=0;wr_gray_r1<=0;wr_gray_r2<=0;rd_valid<=0;
        end else begin
            wr_gray_r1<=wr_gray;wr_gray_r2<=wr_gray_r1;
            rd_valid<=rd_en && rd_ready;
            if(rd_en && rd_ready) begin
                rd_binary<=next_rd;rd_gray<=(next_rd>>1)^next_rd;
            end
        end
    end
    // No memory/output reset: enables true dual-port block-RAM inference.
    always @(posedge rd_clk)
        if(rd_en && rd_ready) rd_data<=memory[rd_binary[ADDR_BITS-1:0]];
endmodule
