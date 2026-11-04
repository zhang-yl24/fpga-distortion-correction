`timescale 1ns/1ps
// One held source mailbox plus one local packet slot. Acknowledge AFTER a local
// atomic copy, not after serial transmission. No packet can mix source records.
// A packet-level UART owner must retain ownership through final byte_done.
module signature_packet_tx(
    input wire tx_clk,rst_n,
    input wire [959:0] mailbox_data,
    input wire mailbox_request,
    output reg mailbox_ack,
    output wire byte_valid,
    output wire [7:0] byte_data,
    input wire byte_ready,byte_done,
    output reg packet_active,
    output reg packet_done
);
    `include "reuse/crc_byte.vh"
    (* PAP_ASYNC_REG=1 *) reg [1:0] release_sync=0,request_sync=0;
    reg [959:0] held;
    reg [7:0] index;
    reg [31:0] crc;
    reg tail_wait;
    wire [31:0] tail=32'h31304753; // "SG01"
    always @(posedge tx_clk or negedge rst_n)
        if(!rst_n)release_sync<=0;else release_sync<={release_sync[0],1'b1};
    assign byte_valid=packet_active && !tail_wait;
    assign byte_data=index<120 ? held[index*8+:8]:
        (index<124 ? (~crc)>>((index-120)*8):tail>>((index-124)*8));
    always @(posedge tx_clk or negedge rst_n)begin
        if(!rst_n)begin
            request_sync<=0;mailbox_ack<=0;held<=0;index<=0;crc<=32'hffffffff;
            tail_wait<=0;packet_active<=0;packet_done<=0;
        end else if(!release_sync[1])begin
            request_sync<=0;mailbox_ack<=0;held<=0;index<=0;crc<=32'hffffffff;
            tail_wait<=0;packet_active<=0;packet_done<=0;
        end else begin
            request_sync<={request_sync[0],mailbox_request};packet_done<=0;
            if(!packet_active && request_sync[1]!=mailbox_ack)begin
                held<=mailbox_data;mailbox_ack<=request_sync[1];
                index<=0;crc<=32'hffffffff;tail_wait<=0;packet_active<=1;
            end
            if(byte_valid && byte_ready)begin
                if(index<120)crc<=crc_byte(crc,byte_data);
                if(index==127)tail_wait<=1;else index<=index+1'b1;
            end
            if(packet_active && tail_wait && byte_done)begin
                packet_active<=0;tail_wait<=0;packet_done<=1;
            end
        end
    end
endmodule
