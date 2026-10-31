`timescale 1ns/1ps
// Isolated diagnostic for observer freshness. No DDR, camera or correction.
module hdmi_uart_rearm_diag #(
    parameter integer CFG_SETTLE_CYCLES=2700000
)(
    input clk_27m, reset_n, pixclk_in, vs_in, hs_in, de_in,
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
    wire peripheral_reset_n=reset_n && power_ready;
    assign rstn_out=peripheral_reset_n;
    reg [31:0] configuration_wait_count=0;
    reg configuration_ready=0;
    always @(posedge clk_27m or negedge peripheral_reset_n) begin
        if(!peripheral_reset_n) begin
            configuration_wait_count<=0; configuration_ready<=0;
        end else if(!configuration_ready) begin
            if(configuration_wait_count<CFG_SETTLE_CYCLES-1)
                configuration_wait_count<=configuration_wait_count+1'b1;
            else configuration_ready<=1;
        end
    end
    wire configuration_reset_n=peripheral_reset_n && configuration_ready;
    wire cfg_clk,cfg_lock,video_lock;
    cfg_pll configuration_pll(.clkin1(clk_27m),.clkout0(cfg_clk),.lock(cfg_lock));
    bringup_pll video_pll(.clkin1(clk_27m),.clkout0(pix_clk),.lock(video_lock));
    wire rx_done,tx_done,cfg_failed;
    wire [3:0] cfg_error;
    wire [31:0] transactions;
    wire [15:0] last_address;
    wire [7:0] last_value;
    wire [1:0] last_meta;
    ms72xx_rearm_observed_ctl hdmi_configuration(
        .clk(cfg_clk),.rst_n(configuration_reset_n),
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
    wire observer_reset_n=peripheral_reset_n && rx_done_ref[1];
    wire input_qualified,input_failed,polarity_known,vs_inactive,hs_inactive;
    wire pclk_fresh,vsync_fresh,href_fresh,frame_fresh,snapshot_fresh;
    wire [15:0] vs_edge_count_ref;
    wire [7:0] input_fault;
    wire [31:0] good_frames,bad_frames,pclk_edges;
    wire [15:0] measured_width,measured_height;
    hdmi1080_input_status_interval_trained input_status(
        .ref_clk(clk_27m),.pix_clk(pixclk_in),.rst_n(observer_reset_n),
        .pix_vs(vs_in),.pix_hs(hs_in),.pix_de(de_in),.normalized_vs(),
        .qualified(input_qualified),.failed(input_failed),.fault(input_fault),
        .polarity_known_ref(polarity_known),.vs_inactive_ref(vs_inactive),.hs_inactive_ref(hs_inactive),
        .good_frames(good_frames),.bad_frames(bad_frames),.pclk_edges_per_window(pclk_edges),
        .last_pixels_per_line(measured_width),.last_lines(measured_height),
        .pclk_fresh_ref(pclk_fresh),.vsync_fresh_ref(vsync_fresh),.href_fresh_ref(href_fresh),
        .frame_fresh_ref(frame_fresh),.snapshot_fresh_ref(snapshot_fresh),
        .vs_edge_count_ref(vs_edge_count_ref));
    wire pattern_arst_n=peripheral_reset_n && video_lock;
    (* async_reg="true" *) reg [1:0] pattern_reset=0;
    always @(posedge pix_clk or negedge pattern_arst_n)
        if(!pattern_arst_n) pattern_reset<=0;
        else pattern_reset<={pattern_reset[0],1'b1};
    video_pattern #(.MODE_720P(0)) pattern(.clk(pix_clk),.rst_n(pattern_reset[1]),
        .hs(hs_out),.vs(vs_out),.de(de_out),.r(r_out),.g(g_out),.b(b_out));
    hdmi_diag_uart_v3 telemetry(
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
        .observer_freshness({snapshot_fresh,frame_fresh,href_fresh,vsync_fresh,pclk_fresh}),
        .vs_edge_count_ref(vs_edge_count_ref),
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
