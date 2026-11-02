`timescale 1ns/1ps
// ACK priority only at packet boundaries; ownership never changes mid-packet.
module telemetry_packet_arbiter #(parameter SNAPSHOT_ENABLE=0)(
    input wire clk,rst_n,input wire snapshot_hold,
    input wire ack_pending,ack_active,ack_valid,ack_packet_done,input wire [7:0] ack_data,
    output wire ack_ready,ack_byte_done,
    input wire signature_active,signature_valid,signature_packet_done,input wire [7:0] signature_data,
    output wire signature_ready,signature_byte_done,
    output wire tx_valid,output wire [7:0] tx_data,input wire tx_ready,tx_done,
    output reg [1:0] owner
);
    localparam IDLE=0,ACK=1,SIGNATURE=2;
    (* PAP_ASYNC_REG=1 *) reg [1:0] release_sync=0;
    assign tx_valid=owner==ACK?ack_valid:owner==SIGNATURE?signature_valid:1'b0;
    assign tx_data=owner==ACK?ack_data:owner==SIGNATURE?signature_data:8'b0;
    assign ack_ready=owner==ACK && tx_ready;
    assign ack_byte_done=owner==ACK && tx_done;
    assign signature_ready=owner==SIGNATURE && tx_ready;
    assign signature_byte_done=owner==SIGNATURE && tx_done;
    always @(posedge clk or negedge rst_n)
        if(!rst_n)release_sync<=0;else release_sync<={release_sync[0],1'b1};
    always @(posedge clk or negedge rst_n)begin
        if(!rst_n)owner<=IDLE;
        else if(!release_sync[1])owner<=IDLE;
        else case(owner)
            IDLE:if(!SNAPSHOT_ENABLE || !snapshot_hold)begin
                if(ack_active)owner<=ACK;
                else if(!ack_pending && signature_active)owner<=SIGNATURE;
            end
            ACK:if(ack_packet_done)owner<=IDLE;
            SIGNATURE:if(signature_packet_done)owner<=IDLE;
            default:owner<=IDLE;
        endcase
    end
endmodule
