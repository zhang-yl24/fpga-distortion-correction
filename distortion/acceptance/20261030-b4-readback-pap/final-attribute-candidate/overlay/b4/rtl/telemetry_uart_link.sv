`timescale 1ns/1ps
// Optional raw logic-level UART wrapper; NO physical pin or IO constraints.
// UART engines are exact project-owned snapshots, with explicit clock/baud.
module telemetry_uart_link #(
    parameter integer WIDTH=1920,HEIGHT=1080,CLOCK_HZ=27000000,BAUD=115200,
    RX_TIMEOUT_CYCLES=CLOCK_HZ/10
)(
    input wire ctrl_clk,pix_clk,rst_n,uart_rx,output wire uart_tx,
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
    uart_rx_control #(.CLOCK_HZ(CLOCK_HZ),.BAUD(BAUD)) receiver(
        .clk(ctrl_clk),.rst_n(uart_release[1]),.rx(uart_rx),
        .valid(rx_valid),.data(rx_data),.framing_error(rx_error));
    uart_tx #(.CLOCK_HZ(CLOCK_HZ),.BAUD(BAUD)) transmitter(
        .clk(ctrl_clk),.rst_n(uart_release[1]),.start(tx_valid && !tx_busy),.data(tx_data),
        .tx(uart_tx),.busy(tx_busy),.done(tx_done));
    telemetry_session_link #(.WIDTH(WIDTH),.HEIGHT(HEIGHT),.CTRL_HZ(CLOCK_HZ),
        .RX_TIMEOUT_CYCLES(RX_TIMEOUT_CYCLES)) link(
        .ctrl_clk(ctrl_clk),.pix_clk(pix_clk),.rst_n(rst_n),.rx_valid(rx_valid),.rx_error(rx_error),.rx_data(rx_data),
        .tx_valid(tx_valid),.tx_data(tx_data),.tx_ready(!tx_busy),.tx_done(tx_done),
        .pixel_valid(pixel_valid),.frame_start(frame_start),.frame_last(frame_last),.video_abort(video_abort),
        .pixel_x(pixel_x),.pixel_y(pixel_y),.pixel_rgb(pixel_rgb),.metadata_valid(metadata_valid),
        .scan_epoch(scan_epoch),.frame_id(frame_id),.param_id(param_id),.bank(bank),.mode(mode),
        .rx_queued(rx_queued),.rx_rejected(rx_rejected),.rx_busy_drops(rx_busy_drops),
        .rx_timeouts(rx_timeouts),.rx_framing_errors(),.signature_dropped(signature_dropped),
        .signature_aborted(),.signature_malformed(),.tx_owner());
endmodule
