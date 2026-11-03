`timescale 1ns/1ps
// Frozen 24-byte SGK1 ACK; packet_active extends through final UART stop done.
module arm_ack_tx(
    input wire clk,rst_n,ack_valid,output wire ack_ready,
    input wire [31:0] ack_ticket,ack_nonce,ack_epoch,input wire [7:0] ack_status,
    output wire byte_valid,output wire [7:0] byte_data,input wire byte_ready,byte_done,
    output reg packet_active,packet_done
);
    `include "crc_byte.vh"
    (* PAP_ASYNC_REG=1 *) reg [1:0] release_sync=0;
    reg [159:0] held;
    reg [4:0] index;
    reg [31:0] crc;
    reg tail_wait;
    assign ack_ready=release_sync[1] && !packet_active;
    assign byte_valid=packet_active && !tail_wait;
    assign byte_data=index<20?held[index*8+:8]:(~crc)>>((index-20)*8);
    always @(posedge clk or negedge rst_n)
        if(!rst_n)release_sync<=0;else release_sync<={release_sync[0],1'b1};
    always @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin held<=0;index<=0;crc<=32'hffffffff;tail_wait<=0;packet_active<=0;packet_done<=0;end
        else if(!release_sync[1])begin held<=0;index<=0;crc<=32'hffffffff;tail_wait<=0;packet_active<=0;packet_done<=0;end
        else begin
            packet_done<=0;
            if(ack_valid && ack_ready)begin
                held<={ack_epoch,ack_nonce,ack_ticket,16'd24,ack_status,8'd1,32'h314b4753};
                index<=0;crc<=32'hffffffff;tail_wait<=0;packet_active<=1;
            end
            if(byte_valid && byte_ready)begin
                if(index<20)crc<=crc_byte(crc,byte_data);
                if(index==23)tail_wait<=1;else index<=index+1'b1;
            end
            if(packet_active && tail_wait && byte_done)begin packet_active<=0;tail_wait<=0;packet_done<=1;end
        end
    end
endmodule
