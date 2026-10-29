`timescale 1ns/1ps
// Independent configuration-only HDMI diagnostic: checked I2C + TX test bars
// and UART telemetry. No input observer, DDR, camera, or lens correction.
// TX bars are synthetic 1920x1080p30 at nominal 74.25MHz, never camera output.
module hdmi_uart_control_diag(
    input clk_27m, reset_n,
    inout hd_scl, hd_sda,
    output rstn_out, uart_txd,
    output pix_clk, hs_out, vs_out, de_out,
    output [7:0] r_out, g_out, b_out, led
);
    (* async_reg="true" *) reg [1:0] ref_reset=0;
    always @(posedge clk_27m or negedge reset_n)
        if(!reset_n) ref_reset<=0; else ref_reset<={ref_reset[0],1'b1};
    reg [19:0] power_count=0;
    reg power_ready=0;
    always @(posedge clk_27m or negedge reset_n) begin
        if(!reset_n) begin power_count<=0; power_ready<=0; end
        else if(!ref_reset[1]) begin power_count<=0; power_ready<=0; end
        else if(!(&power_count)) power_count<=power_count+1'b1;
        else power_ready<=1;
    end
    // G25 is the board's shared peripheral reset, including an Ethernet PHY.
    wire peripheral_reset_n=reset_n && power_ready;
    assign rstn_out=peripheral_reset_n;
    wire cfg_clk,cfg_lock,video_lock;
    cfg_pll configuration_pll(.clkin1(clk_27m),.clkout0(cfg_clk),.lock(cfg_lock));
    bringup_pll video_pll(.clkin1(clk_27m),.clkout0(pix_clk),.lock(video_lock));
    wire rx_done,tx_done,cfg_failed;
    wire [3:0] cfg_error;
    wire [31:0] transactions;
    wire [15:0] last_address;
    wire [7:0] last_value;
    wire [1:0] last_meta;
    ms72xx_observed_ctl hdmi_configuration(
        .clk(cfg_clk),.rst_n(peripheral_reset_n),
        .init_over_rx(rx_done),.init_over(tx_done),
        .init_failed(cfg_failed),.error_code(cfg_error),
        .iic_scl(hd_scl),.iic_sda(hd_sda),
        .completed_transactions(transactions),.last_address(last_address),
        .last_value(last_value),.last_meta(last_meta));
    (* async_reg="true" *) reg [1:0] cfg_lock_ref=0,video_lock_ref=0,rx_done_ref=0;
    (* async_reg="true" *) reg [1:0] tx_done_ref=0,cfg_failed_ref=0;
    always @(posedge clk_27m or negedge reset_n) begin
        if(!reset_n) begin
            cfg_lock_ref<=0;video_lock_ref<=0;rx_done_ref<=0;tx_done_ref<=0;cfg_failed_ref<=0;
        end else if(!ref_reset[1]) begin
            cfg_lock_ref<=0;video_lock_ref<=0;rx_done_ref<=0;tx_done_ref<=0;cfg_failed_ref<=0;
        end else begin
            cfg_lock_ref<={cfg_lock_ref[0],cfg_lock};video_lock_ref<={video_lock_ref[0],video_lock};
            rx_done_ref<={rx_done_ref[0],rx_done};tx_done_ref<={tx_done_ref[0],tx_done};
            cfg_failed_ref<={cfg_failed_ref[0],cfg_failed};
        end
    end
    // No input observer in this first on-board configuration diagnostic.
    // Zero monitor fields mean unavailable, never zero measured video.
    wire observer_reset_n=1'b0;
    wire input_qualified=1'b0,input_failed=1'b0,polarity_known=1'b0;
    wire vs_inactive=1'b0,hs_inactive=1'b0;
    wire [7:0] input_fault=8'd0;
    wire [31:0] good_frames=0,bad_frames=0,pclk_edges=0;
    wire [15:0] measured_width=0,measured_height=0;
    // The unmodified pattern uses 2200x1125 with MODE_720P=0. This PLL is
    // 74.25MHz, so its output is 30 fps (the module's 60 fps comment assumes
    // a different clock). Pattern timing has no dependence on HDMI input.
    wire pattern_arst_n=peripheral_reset_n && video_lock;
    (* async_reg="true" *) reg [1:0] pattern_reset=0;
    always @(posedge pix_clk or negedge pattern_arst_n)
        if(!pattern_arst_n) pattern_reset<=0;
        else pattern_reset<={pattern_reset[0],1'b1};
    video_pattern #(.MODE_720P(0)) pattern(.clk(pix_clk),.rst_n(pattern_reset[1]),
        .hs(hs_out),.vs(vs_out),.de(de_out),.r(r_out),.g(g_out),.b(b_out));
    // UART remains alive before peripheral initialization and if cfg_clk
    // stops. Missing/stale cfg snapshots are explicitly marked by the codec.
    hdmi_diag_uart telemetry(
        .cfg_clk(cfg_clk),.ref_clk(clk_27m),.rst_n(reset_n && ref_reset[1]),
        .cfg_rx_done(rx_done),.cfg_all_done(tx_done),.cfg_failed(cfg_failed),.cfg_error(cfg_error),
        .cfg_transactions(transactions),.cfg_last_address(last_address),
        .cfg_last_value(last_value),.cfg_last_meta(last_meta),
        .cfg_lock_ref(cfg_lock_ref[1]),.video_lock_ref(video_lock_ref[1]),
        .observer_released(observer_reset_n),.input_qualified(input_qualified),
        .input_failed(input_failed),.input_fault(input_fault),
        .polarity_known_ref(polarity_known),.vs_inactive_ref(vs_inactive),.hs_inactive_ref(hs_inactive),
        .measured_width(measured_width),.measured_height(measured_height),
        .pclk_edges_per_window(pclk_edges),.good_frames(good_frames),.bad_frames(bad_frames),
        .uart_txd(uart_txd),.record_started(),.record_done(),.record_sequence());
    reg [23:0] heart_count=0;
    reg heartbeat=0;
    always @(posedge clk_27m) begin
        if(!ref_reset[1]) begin heart_count<=0;heartbeat<=0;end
        else if(heart_count==13499999) begin heart_count<=0;heartbeat<=!heartbeat;end
        else heart_count<=heart_count+1'b1;
    end
    assign led={cfg_failed_ref[1] || input_failed,input_qualified,tx_done_ref[1],rx_done_ref[1],
                video_lock_ref[1],cfg_lock_ref[1],power_ready,heartbeat};
endmodule
