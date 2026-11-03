// Isolated source candidate: ready-at-start RX and complete-line polarity training.
// Requires its own native build/CDC/STA/bitstream validation before programming.
// Diagnostic copy of ms72xx_checked_ctl: only telemetry ports/taps added.
`timescale 1ns/1ps
// Isolated development unit; not selected by any accepted board build.
// Compile with ms7200_1080p30_ctl.v (module ms7200_ctl), the unchanged
// ms7210_checked_ctl.v and iic_dri_checked.v. Both bus pins need pullups.
// init_over means checked register transactions completed, NOT PHY lock,
// negotiated RGB/SDR mode, correct video, or physical timing acceptance.
module ms72xx_rearm_observed_ctl #(
    parameter integer CLK_FRE = 10000000,
    parameter integer IIC_FREQ = 400000,
    parameter integer TIMEOUT_CYCLES = CLK_FRE / 100
)(
    input wire clk,
    input wire rst_n,
    output wire init_over_rx,
    output wire init_over,
    output wire init_failed,
    output wire [3:0] error_code,
    inout wire iic_scl,
    inout wire iic_sda,
    output reg [31:0] completed_transactions,
    output reg [15:0] last_address,
    output reg [7:0] last_value,
    output reg [1:0] last_meta
);
    // Asynchronous assertion, synchronous release in the configuration domain.
    (* PAP_ASYNC_REG=1, syn_srlstyle="registers" *) reg [2:0] cfg_reset_pipe;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) cfg_reset_pipe <= 3'b000;
        else cfg_reset_pipe <= {cfg_reset_pipe[1:0], 1'b1};
    end
    wire cfg_rst_n = cfg_reset_pipe[2];
    wire driver_failed;
    wire [3:0] driver_error;
    reg failed_latched;
    reg [3:0] error_latched;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            failed_latched <= 1'b0;
            error_latched <= 4'h0;
        end else if (!failed_latched && driver_failed) begin
            failed_latched <= 1'b1;
            error_latched <= driver_error;
        end
    end
    // Raw failure gates completion in the SAME cycle busy drops on error.
    // The driver remains under global reset only: resetting it on its own
    // failure would clear the evidence and create an unintended retry loop.
    wire failed = driver_failed | failed_latched;
    assign init_failed = cfg_rst_n && failed;
    assign error_code = !cfg_rst_n ? 4'h0 :
                        (failed_latched ? error_latched : driver_error);
    wire seq_async_rst_n = rst_n && !failed;
    (* PAP_ASYNC_REG=1, syn_srlstyle="registers" *) reg [2:0] seq_reset_pipe;
    always @(posedge clk or negedge seq_async_rst_n) begin
        if (!seq_async_rst_n) seq_reset_pipe <= 3'b000;
        else seq_reset_pipe <= {seq_reset_pipe[1:0], cfg_rst_n};
    end
    wire seq_rst_n = seq_reset_pipe[2] && cfg_rst_n && !failed;
    wire rx_done, tx_done;
    wire tx_async_rst_n = seq_rst_n && rx_done;
    (* PAP_ASYNC_REG=1, syn_srlstyle="registers" *) reg [2:0] tx_reset_pipe;
    always @(posedge clk or negedge tx_async_rst_n) begin
        if (!tx_async_rst_n) tx_reset_pipe <= 3'b000;
        else tx_reset_pipe <= {tx_reset_pipe[1:0], 1'b1};
    end
    wire tx_rst_n = tx_reset_pipe[2] && tx_async_rst_n;
    assign init_over_rx = seq_rst_n && rx_done;
    assign init_over = seq_rst_n && tx_rst_n && rx_done && tx_done;

    wire rx_trig, rx_wr, tx_trig, tx_wr;
    wire [15:0] rx_addr, tx_addr;
    wire [7:0] rx_data, tx_data;
    wire driver_busy, driver_byte_over;
    wire [7:0] driver_data;
    wire tx_selected = rx_done && !tx_done;
    // Preserve the reference ownership rule: RX -> TX init -> RX polling.
    // Source sequencers have synchronous internal reset; seq_rst_n asserts
    // immediately, while their state resets at the next clk. Output/request
    // gates prevent any transient successful completion during that interval.
    ms7200_1080p30_rearm_ctl rx_controller (
        .clk(clk), .rstn(seq_rst_n), .init_over(rx_done), .device_id(),
        .iic_trig(rx_trig), .w_r(rx_wr), .addr(rx_addr), .data_in(rx_data),
        .busy(!tx_selected ? driver_busy : 1'b0),
        .data_out(!tx_selected ? driver_data : 8'h00),
        .byte_over(!tx_selected && !failed ? driver_byte_over : 1'b0)
    );
    ms7210_checked_ctl tx_controller (
        .clk(clk), .rstn(tx_rst_n), .init_over(tx_done), .device_id(),
        .iic_trig(tx_trig), .w_r(tx_wr), .addr(tx_addr), .data_in(tx_data),
        .busy(tx_selected ? driver_busy : 1'b0),
        .data_out(tx_selected ? driver_data : 8'h00),
        .byte_over(tx_selected && !failed ? driver_byte_over : 1'b0)
    );
    // RX's first status-read request occurs when it hands the bus to TX and
    // is intentionally masked then. Resume that pending read once TX is done.
    // This is a request pulse, never a synthetic busy/completion pulse.
    reg tx_done_previous;
    always @(posedge clk or negedge seq_rst_n) begin
        if (!seq_rst_n) tx_done_previous <= 1'b0;
        else tx_done_previous <= tx_done;
    end
    wire resume_rx = tx_done && !tx_done_previous && !driver_busy;
    wire driver_trig = seq_rst_n && !failed &&
                       (tx_selected ? (tx_rst_n && tx_trig) : (rx_trig || resume_rx));
    wire scl_release, sda_out, sda_out_en;
    iic_dri_checked #(
        .CLK_FRE(CLK_FRE), .IIC_FREQ(IIC_FREQ), .T_WR(1),
        .ADDR_BYTE(2), .LEN_WIDTH(3), .DATA_BYTE(1),
        .TIMEOUT_CYCLES(TIMEOUT_CYCLES)
    ) driver (
        .clk(clk), .rstn(cfg_rst_n), .pluse(driver_trig),
        .device_id(tx_selected ? 8'hB2 : 8'h56),
        .w_r(tx_selected ? tx_wr : rx_wr), .byte_len(4'd1),
        .addr(tx_selected ? tx_addr : rx_addr),
        .data_in(tx_selected ? tx_data : rx_data),
        .busy(driver_busy), .byte_over(driver_byte_over), .data_out(driver_data),
        .scl(scl_release), .scl_in(iic_scl), .sda_in(iic_sda),
        .sda_out(sda_out), .sda_out_en(sda_out_en),
        .transaction_failed(driver_failed), .error_code(driver_error)
    );
    // Top-level SCL must also become an inout for stretching/stuck-bus checks;
    // the legacy board top output-only hd_scl is not a drop-in integration.
    assign iic_scl = scl_release ? 1'bz : 1'b0;
    assign iic_sda = sda_out_en ? sda_out : 1'bz;

    // Read-only taps; no feedback into requests, resets or sequencers.
    // Latch transaction metadata on actual busy rising, after the driver's
    // trigger pipeline accepts it. byte_over is success only, never a NACK.
    reg observed_busy;
    reg [15:0] active_address;
    reg [7:0] active_write_value;
    reg [1:0] active_meta;
    always @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin
            observed_busy<=0; active_address<=0; active_write_value<=0; active_meta<=0;
            completed_transactions<=0; last_address<=0; last_value<=0; last_meta<=0;
        end else begin
            observed_busy<=driver_busy;
            if(driver_busy && !observed_busy) begin
                active_address<=tx_selected ? tx_addr : rx_addr;
                active_write_value<=tx_selected ? tx_data : rx_data;
                active_meta<={tx_selected,!(tx_selected ? tx_wr : rx_wr)};
            end
            if(driver_byte_over && !failed) begin
                if(completed_transactions!=32'hffffffff)
                    completed_transactions<=completed_transactions+1'b1;
                last_address<=active_address;
                last_value<=active_meta[0] ? driver_data : active_write_value;
                last_meta<=active_meta;
            end
        end
    end
endmodule
