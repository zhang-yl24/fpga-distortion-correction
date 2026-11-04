`timescale 1ns/1ps
// Same final digital scan tap as b1. This wrapper gates only the observer.
// Control/ACK ports are synchronous to pix_clk; physical RX/CDC/TX owner pending.
module scan_signature_armed_v3 #(
    parameter integer WIDTH=1920,HEIGHT=1080
)(
    input wire pix_clk,rst_n,
    input wire load_valid,output wire load_ready,
    input wire [31:0] load_ticket,load_nonce,
    output wire ack_valid,input wire ack_ready,
    output wire [31:0] ack_ticket,ack_nonce,ack_epoch,output wire [7:0] ack_status,
    input wire pixel_valid,frame_start,frame_last,video_abort,
    input wire [15:0] pixel_x,pixel_y,input wire [23:0] pixel_rgb,
    input wire metadata_valid,input wire [31:0] scan_epoch,frame_id,param_id,
    input wire bank,input wire [7:0] mode,
    output wire [959:0] mailbox_data,output wire mailbox_request,input wire mailbox_ack,
    output wire [31:0] dropped,aborted,malformed
);
    wire capture_enable,capture_abort;
    wire [31:0] capture_session;
    session_arm_gate_v3 gate(.pix_clk(pix_clk),.rst_n(rst_n),
        .load_valid(load_valid),.load_ready(load_ready),.load_ticket(load_ticket),.load_nonce(load_nonce),
        .ack_valid(ack_valid),.ack_ready(ack_ready),.ack_ticket(ack_ticket),.ack_nonce(ack_nonce),
        .ack_epoch(ack_epoch),.ack_status(ack_status),.pixel_valid(pixel_valid),.frame_start(frame_start),
        .video_abort(video_abort),.scan_epoch(scan_epoch),.capture_enable(capture_enable),
        .capture_abort(capture_abort),.capture_session(capture_session));
    scan_signature_capture #(.WIDTH(WIDTH),.HEIGHT(HEIGHT)) capture(
        .pix_clk(pix_clk),.rst_n(rst_n),.pixel_valid(pixel_valid && capture_enable),
        .frame_start(frame_start && capture_enable),.frame_last(frame_last && capture_enable),
        .abort(capture_abort),.pixel_x(pixel_x),.pixel_y(pixel_y),.pixel_rgb(pixel_rgb),
        .metadata_valid(metadata_valid),.session_id(capture_session),.scan_epoch(scan_epoch),
        .frame_id(frame_id),.param_id(param_id),.bank(bank),.mode(mode),
        .mailbox_data(mailbox_data),.mailbox_request(mailbox_request),.mailbox_ack(mailbox_ack),
        .dropped(dropped),.aborted(aborted),.malformed(malformed));
endmodule
