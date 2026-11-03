`timescale 1ns/1ps
// Uses existing SG* version/nonce/CRC parser and held-bundle CDC. It can own
// UART only between COMPLETE packets and outside the entire snapshot session.
module stats_uart_mux #(
    parameter integer RX_TIMEOUT_CYCLES=2700000,LIGHT=0,BODY_BITS=LIGHT ? 640:1120
)(
    input ctrl_clk,core_clk,rst_n,input rx_valid,rx_error,input [7:0] rx_data,
    output request_valid,input request_ready,output [31:0] ticket,nonce,
    input response_valid,output response_ready,input [BODY_BITS-1:0] response_body,
    input b4_packet_idle,snapshot_hold,snapshot_owner,
    output hold_b4,output reg owner,
    output tx_valid,output [7:0] tx_data,input tx_ready,tx_done
);
    `include "reuse/crc_byte.vh"
    wire cmd_valid,cmd_ready,cross_ready;wire [31:0] cmd_ticket,cmd_nonce;
    reg request_inflight;
    snapshot_command_parser #(.MAGIC(32'h31544753),.BYTE_TIMEOUT_CYCLES(RX_TIMEOUT_CYCLES)) parser(
        .clk(ctrl_clk),.rst_n(rst_n),.rx_valid(rx_valid),.rx_error(rx_error),.rx_data(rx_data),
        .cmd_valid(cmd_valid),.cmd_ready(cmd_ready),.cmd_ticket(cmd_ticket),.cmd_nonce(cmd_nonce),
        .queued(),.rejected(),.busy_drops(),.timeouts(),.framing_errors());
    // A full parser slot drops further commands as before; one active request
    // plus at most one parser slot. No effect on RX or video backpressure.
    assign cmd_ready=cross_ready && !request_inflight;
    held_bundle_cdc #(.WIDTH(64)) request_cross(
        .s_clk(ctrl_clk),.d_clk(core_clk),.rst_n(rst_n),
        .s_valid(cmd_valid && !request_inflight),.s_ready(cross_ready),.s_data({cmd_nonce,cmd_ticket}),
        .d_valid(request_valid),.d_ready(request_ready),.d_data({nonce,ticket}));
    localparam BODY_BYTES=LIGHT ? 80:140,PACKET_BYTES=BODY_BYTES+4;
    wire body_valid,body_done;wire [BODY_BITS-1:0] body;
    held_completion_cdc #(.WIDTH(BODY_BITS)) response_cross(
        .s_clk(core_clk),.d_clk(ctrl_clk),.rst_n(rst_n),
        .s_valid(response_valid),.s_ready(response_ready),.s_data(response_body),.s_done(),.s_idle(),
        .d_valid(body_valid),.d_done(body_done),.d_data(body));
    reg tail;reg [7:0] index;reg [31:0] crc;
    assign hold_b4=cmd_valid || request_inflight || body_valid || owner;
    assign tx_valid=owner && !tail;
    assign tx_data=index<BODY_BYTES ? body[index*8+:8]:(~crc)>>((index-BODY_BYTES)*8);
    // Final physical stop bit, not a byte queue acceptance or inter-byte gap.
    assign body_done=owner && tail && tx_done;
    always @(posedge ctrl_clk or negedge rst_n)begin
        if(!rst_n)begin owner<=0;tail<=0;index<=0;crc<=32'hffffffff;request_inflight<=0;end
        else begin
            if(cmd_valid && cmd_ready)request_inflight<=1;
            if(!owner && body_valid && !snapshot_hold && !snapshot_owner && b4_packet_idle && tx_ready)begin
                owner<=1;tail<=0;index<=0;crc<=32'hffffffff;
            end
            if(tx_valid && tx_ready)begin
                if(index<BODY_BYTES)crc<=crc_byte(crc,tx_data);
                if(index==PACKET_BYTES-1)tail<=1;else index<=index+1'b1;
            end
            if(body_done)begin owner<=0;tail<=0;request_inflight<=0;end
        end
    end
endmodule
