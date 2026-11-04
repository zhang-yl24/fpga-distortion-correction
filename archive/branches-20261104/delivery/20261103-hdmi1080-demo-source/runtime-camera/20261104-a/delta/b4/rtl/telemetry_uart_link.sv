`timescale 1ns/1ps
// Optional raw logic-level UART wrapper; NO physical pin or IO constraints.
// UART engines are exact project-owned snapshots, with explicit clock/baud.
module telemetry_uart_link #(
    parameter integer WIDTH=1920,HEIGHT=1080,CLOCK_HZ=27000000,BAUD=115200,
    RX_TIMEOUT_CYCLES=CLOCK_HZ/10,SNAPSHOT_ENABLE=0,STATS_ENABLE=0,STATS_LIGHT=0,
    STATS_BODY_BITS=STATS_LIGHT ? 640:1120,ENABLE_RUNTIME_ROTATION=0
)(
    input wire ctrl_clk,pix_clk,rst_n,uart_rx,output wire uart_tx,
    input wire snapshot_core_clk,
    input wire [31:0] rotation_base_param_id,
    output wire rotation_config_valid,input wire rotation_config_ready,output wire [127:0] rotation_config_data,
    output wire stats_request_valid,input wire stats_request_ready,output wire [31:0] stats_ticket,stats_nonce,
    input wire stats_response_valid,output wire stats_response_ready,input wire [STATS_BODY_BITS-1:0] stats_response_body,
    output wire snapshot_request_valid,input wire snapshot_request_ready,
    output wire [31:0] snapshot_ticket,snapshot_nonce,
    output wire snapshot_stop_valid,input wire snapshot_stop_ready,
    output wire [31:0] snapshot_stop_ticket,snapshot_stop_nonce,
    input wire snapshot_ack_valid,output wire snapshot_ack_ready,snapshot_ack_done,
    input wire [351:0] snapshot_ack_body,
    input wire snapshot_byte_valid,input wire [7:0] snapshot_byte_data,
    output wire snapshot_byte_ready,snapshot_byte_done,snapshot_byte_idle,
    input wire snapshot_release_valid,output wire snapshot_release_ready,snapshot_release_done,
    input wire pixel_valid,frame_start,frame_last,video_abort,
    input wire [15:0] pixel_x,pixel_y,input wire [23:0] pixel_rgb,
    input wire metadata_valid,input wire [31:0] scan_epoch,frame_id,param_id,
    input wire bank,input wire [7:0] mode,
    output wire [31:0] rx_queued,rx_rejected,rx_busy_drops,rx_timeouts,signature_dropped
);
    (* PAP_ASYNC_REG=1 *) reg [1:0] uart_release=0;
    always @(posedge ctrl_clk or negedge rst_n)
        if(!rst_n)uart_release<=0;else uart_release<={uart_release[0],1'b1};
    wire rx_valid,rx_error,tx_valid,tx_busy,tx_done;
    wire [7:0] rx_data,tx_data;
    wire routed_rx_valid,routed_rx_error;wire [7:0] routed_rx_data;
    wire b4_valid,b4_idle,snapshot_hold,snapshot_owner,snapshot_tx_valid;
    wire [7:0] b4_data,snapshot_tx_data;
    wire stats_hold,stats_owner,stats_tx_valid;wire [7:0] stats_tx_data;
    assign tx_valid=stats_owner ? stats_tx_valid:snapshot_owner ? snapshot_tx_valid:b4_valid;
    assign tx_data=stats_owner ? stats_tx_data:snapshot_owner ? snapshot_tx_data:b4_data;
    generate if(STATS_ENABLE)begin: stats_enabled
        stats_uart_mux #(.RX_TIMEOUT_CYCLES(RX_TIMEOUT_CYCLES),.LIGHT(STATS_LIGHT)) mux(
            .ctrl_clk(ctrl_clk),.core_clk(snapshot_core_clk),.rst_n(rst_n),
            .rx_valid(routed_rx_valid),.rx_error(routed_rx_error),.rx_data(routed_rx_data),
            .request_valid(stats_request_valid),.request_ready(stats_request_ready),.ticket(stats_ticket),.nonce(stats_nonce),
            .response_valid(stats_response_valid),.response_ready(stats_response_ready),.response_body(stats_response_body),
            .b4_packet_idle(b4_idle),.snapshot_hold(snapshot_hold),.snapshot_owner(snapshot_owner),
            .hold_b4(stats_hold),.owner(stats_owner),.tx_valid(stats_tx_valid),.tx_data(stats_tx_data),
            .tx_ready(!tx_busy),.tx_done(tx_done));
    end else begin: stats_disabled
        assign stats_request_valid=0;assign stats_ticket=0;assign stats_nonce=0;assign stats_response_ready=0;
        assign stats_hold=0;assign stats_owner=0;assign stats_tx_valid=0;assign stats_tx_data=0;
    end endgenerate
    generate if(SNAPSHOT_ENABLE) begin: snapshot_enabled
        snapshot_uart_mux mux(
            .ctrl_clk(ctrl_clk),.core_clk(snapshot_core_clk),.rst_n(rst_n),
            .rx_valid(routed_rx_valid),.rx_error(routed_rx_error),.rx_data(routed_rx_data),
            .request_valid(snapshot_request_valid),.request_ready(snapshot_request_ready),
            .ticket(snapshot_ticket),.nonce(snapshot_nonce),
            .stop_valid(snapshot_stop_valid),.stop_ready(snapshot_stop_ready),
            .stop_ticket(snapshot_stop_ticket),.stop_nonce(snapshot_stop_nonce),
            .ack_valid(snapshot_ack_valid),.ack_ready(snapshot_ack_ready),.ack_body(snapshot_ack_body),.ack_done(snapshot_ack_done),
            .frame_valid(snapshot_byte_valid),.frame_data(snapshot_byte_data),
            .frame_ready(snapshot_byte_ready),.frame_done(snapshot_byte_done),.frame_idle(snapshot_byte_idle),
            .release_valid(snapshot_release_valid),.release_ready(snapshot_release_ready),.release_done(snapshot_release_done),
            .b4_packet_idle(b4_idle && !stats_owner),.hold_b4(snapshot_hold),.owner(snapshot_owner),
            .tx_valid(snapshot_tx_valid),.tx_data(snapshot_tx_data),.tx_ready(!tx_busy && !stats_owner),.tx_done(tx_done && !stats_owner));
    end else begin: snapshot_disabled
        assign snapshot_request_valid=0;assign snapshot_ticket=0;assign snapshot_nonce=0;
        assign snapshot_stop_valid=0;assign snapshot_stop_ticket=0;assign snapshot_stop_nonce=0;
        assign snapshot_ack_ready=0;assign snapshot_ack_done=0;
        assign snapshot_byte_ready=0;assign snapshot_byte_done=0;assign snapshot_byte_idle=1;
        assign snapshot_release_ready=0;assign snapshot_release_done=0;
        assign snapshot_hold=0;assign snapshot_owner=0;assign snapshot_tx_valid=0;assign snapshot_tx_data=0;
    end endgenerate
    uart_rx_control #(.CLOCK_HZ(CLOCK_HZ),.BAUD(BAUD)) receiver(
        .clk(ctrl_clk),.rst_n(uart_release[1]),.rx(uart_rx),
        .valid(rx_valid),.data(rx_data),.framing_error(rx_error));
    // Preserve all current consumers and TX arbitration. Only the new optional
    // framed prefilter separates SGR1; its legacy output is byte-exact.
    generate if(ENABLE_RUNTIME_ROTATION)begin: rotation_protocol
        uart_rotation_router #(.BYTE_TIMEOUT_CYCLES(RX_TIMEOUT_CYCLES)) router(
            .clk(ctrl_clk),.rst_n(uart_release[1]),.rx_valid(rx_valid),.rx_error(rx_error),.rx_data(rx_data),
            .base_param_id(rotation_base_param_id),.arm_rx_valid(routed_rx_valid),.arm_rx_error(routed_rx_error),.arm_rx_data(routed_rx_data),
            .config_valid(rotation_config_valid),.config_ready(rotation_config_ready),.config_data(rotation_config_data),
            .config_queued(),.config_rejected(),.config_busy_drops(),.route_overruns());
    end else begin: original_rx_stream
        assign routed_rx_valid=rx_valid;assign routed_rx_error=rx_error;assign routed_rx_data=rx_data;
        assign rotation_config_valid=0;assign rotation_config_data=0;
    end endgenerate

    uart_tx #(.CLOCK_HZ(CLOCK_HZ),.BAUD(BAUD)) transmitter(
        .clk(ctrl_clk),.rst_n(uart_release[1]),.start(tx_valid && !tx_busy),.data(tx_data),
        .tx(uart_tx),.busy(tx_busy),.done(tx_done));
    telemetry_session_link #(.WIDTH(WIDTH),.HEIGHT(HEIGHT),.CTRL_HZ(CLOCK_HZ),
        .RX_TIMEOUT_CYCLES(RX_TIMEOUT_CYCLES),.SNAPSHOT_ENABLE(SNAPSHOT_ENABLE || STATS_ENABLE)) link(
        .ctrl_clk(ctrl_clk),.pix_clk(pix_clk),.rst_n(rst_n),.rx_valid(routed_rx_valid),.rx_error(routed_rx_error),.rx_data(routed_rx_data),
        .tx_valid(b4_valid),.tx_data(b4_data),.tx_ready(!tx_busy && !snapshot_owner && !stats_owner),.tx_done(tx_done && !snapshot_owner && !stats_owner),
        .snapshot_hold(snapshot_hold || stats_hold),.packet_idle(b4_idle),
        .pixel_valid(pixel_valid),.frame_start(frame_start),.frame_last(frame_last),.video_abort(video_abort),
        .pixel_x(pixel_x),.pixel_y(pixel_y),.pixel_rgb(pixel_rgb),.metadata_valid(metadata_valid),
        .scan_epoch(scan_epoch),.frame_id(frame_id),.param_id(param_id),.bank(bank),.mode(mode),
        .rx_queued(rx_queued),.rx_rejected(rx_rejected),.rx_busy_drops(rx_busy_drops),
        .rx_timeouts(rx_timeouts),.rx_framing_errors(),.signature_dropped(signature_dropped),
        .signature_aborted(),.signature_malformed(),.tx_owner());
endmodule
