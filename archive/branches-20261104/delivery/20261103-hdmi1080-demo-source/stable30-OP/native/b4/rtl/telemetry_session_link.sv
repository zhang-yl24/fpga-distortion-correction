`timescale 1ns/1ps
// Complete logical byte-stream -> session/scan capture -> atomic mixed TX link.
// Physical pins and implementation CDC/STA remain outside this source module.
module telemetry_session_link #(
    parameter integer WIDTH=1920,HEIGHT=1080,CTRL_HZ=27000000,SNAPSHOT_ENABLE=0,
    RX_TIMEOUT_CYCLES=CTRL_HZ/10
)(
    input wire ctrl_clk,pix_clk,rst_n,
    input wire snapshot_hold,output wire packet_idle,
    input wire rx_valid,rx_error,input wire [7:0] rx_data,
    output wire tx_valid,output wire [7:0] tx_data,input wire tx_ready,tx_done,
    input wire pixel_valid,frame_start,frame_last,video_abort,
    input wire [15:0] pixel_x,pixel_y,input wire [23:0] pixel_rgb,
    input wire metadata_valid,input wire [31:0] scan_epoch,frame_id,param_id,
    input wire bank,input wire [7:0] mode,
    output wire [31:0] rx_queued,rx_rejected,rx_busy_drops,rx_timeouts,rx_framing_errors,
    output wire [31:0] signature_dropped,signature_aborted,signature_malformed,
    output wire [1:0] tx_owner
);
    wire cmd_valid,cmd_ready;
    wire [31:0] cmd_ticket,cmd_nonce;
    load_arm_parser #(.BYTE_TIMEOUT_CYCLES(RX_TIMEOUT_CYCLES)) parser(
        .clk(ctrl_clk),.rst_n(rst_n),.rx_valid(rx_valid),.rx_error(rx_error),.rx_data(rx_data),
        .cmd_valid(cmd_valid),.cmd_ready(cmd_ready),.cmd_ticket(cmd_ticket),.cmd_nonce(cmd_nonce),
        .queued(rx_queued),.rejected(rx_rejected),.busy_drops(rx_busy_drops),
        .timeouts(rx_timeouts),.framing_errors(rx_framing_errors));
    wire load_valid,load_ready;
    wire [63:0] load_bundle;
    held_bundle_cdc #(.WIDTH(64)) request_cdc(
        .s_clk(ctrl_clk),.d_clk(pix_clk),.rst_n(rst_n),.s_valid(cmd_valid),.s_ready(cmd_ready),
        .s_data({cmd_nonce,cmd_ticket}),.d_valid(load_valid),.d_ready(load_ready),.d_data(load_bundle));
    wire gate_ack_valid,gate_ack_ready;
    wire [31:0] gate_ack_ticket,gate_ack_nonce,gate_ack_epoch;
    wire [7:0] gate_ack_status;
    wire [959:0] mailbox_data;
    wire mailbox_request,mailbox_ack;
    scan_signature_armed_v3 #(.WIDTH(WIDTH),.HEIGHT(HEIGHT)) observer(
        .pix_clk(pix_clk),.rst_n(rst_n),.load_valid(load_valid),.load_ready(load_ready),
        .load_ticket(load_bundle[31:0]),.load_nonce(load_bundle[63:32]),
        .ack_valid(gate_ack_valid),.ack_ready(gate_ack_ready),.ack_ticket(gate_ack_ticket),
        .ack_nonce(gate_ack_nonce),.ack_epoch(gate_ack_epoch),.ack_status(gate_ack_status),
        .pixel_valid(pixel_valid),.frame_start(frame_start),.frame_last(frame_last),.video_abort(video_abort),
        .pixel_x(pixel_x),.pixel_y(pixel_y),.pixel_rgb(pixel_rgb),.metadata_valid(metadata_valid),
        .scan_epoch(scan_epoch),.frame_id(frame_id),.param_id(param_id),.bank(bank),.mode(mode),
        .mailbox_data(mailbox_data),.mailbox_request(mailbox_request),.mailbox_ack(mailbox_ack),
        .dropped(signature_dropped),.aborted(signature_aborted),.malformed(signature_malformed));
    wire reply_valid,reply_ready;
    wire [103:0] reply_bundle;
    held_bundle_cdc #(.WIDTH(104)) ack_cdc(
        .s_clk(pix_clk),.d_clk(ctrl_clk),.rst_n(rst_n),.s_valid(gate_ack_valid),.s_ready(gate_ack_ready),
        .s_data({gate_ack_status,gate_ack_epoch,gate_ack_nonce,gate_ack_ticket}),
        .d_valid(reply_valid),.d_ready(reply_ready),.d_data(reply_bundle));
    wire ack_byte_valid,ack_byte_ready,ack_byte_done,ack_active,ack_done;
    wire [7:0] ack_byte_data;
    arm_ack_tx reply_tx(.clk(ctrl_clk),.rst_n(rst_n),.ack_valid(reply_valid),.ack_ready(reply_ready),
        .ack_ticket(reply_bundle[31:0]),.ack_nonce(reply_bundle[63:32]),
        .ack_epoch(reply_bundle[95:64]),.ack_status(reply_bundle[103:96]),
        .byte_valid(ack_byte_valid),.byte_data(ack_byte_data),.byte_ready(ack_byte_ready),.byte_done(ack_byte_done),
        .packet_active(ack_active),.packet_done(ack_done));
    wire signature_byte_valid,signature_byte_ready,signature_byte_done,signature_active,signature_done;
    wire [7:0] signature_byte_data;
    signature_packet_tx signature_tx(.tx_clk(ctrl_clk),.rst_n(rst_n),
        .mailbox_data(mailbox_data),.mailbox_request(mailbox_request),.mailbox_ack(mailbox_ack),
        .byte_valid(signature_byte_valid),.byte_data(signature_byte_data),
        .byte_ready(signature_byte_ready),.byte_done(signature_byte_done),
        .packet_active(signature_active),.packet_done(signature_done));
    assign packet_idle=tx_owner==0 && tx_ready;
    telemetry_packet_arbiter #(.SNAPSHOT_ENABLE(SNAPSHOT_ENABLE)) tx_arbiter(.clk(ctrl_clk),.rst_n(rst_n),.snapshot_hold(snapshot_hold),
        .ack_pending(reply_valid || ack_active),.ack_active(ack_active),.ack_valid(ack_byte_valid),
        .ack_packet_done(ack_done),.ack_data(ack_byte_data),.ack_ready(ack_byte_ready),.ack_byte_done(ack_byte_done),
        .signature_active(signature_active),.signature_valid(signature_byte_valid),.signature_packet_done(signature_done),
        .signature_data(signature_byte_data),.signature_ready(signature_byte_ready),.signature_byte_done(signature_byte_done),
        .tx_valid(tx_valid),.tx_data(tx_data),.tx_ready(tx_ready),.tx_done(tx_done),.owner(tx_owner));
endmodule
