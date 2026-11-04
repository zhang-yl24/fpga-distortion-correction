`timescale 1ns/1ps
// New HDMI camera calibration C: source -> RGB565 DDR -> fisheye/identity -> 1080p30.
// KEY1 requests a whole-frame mode; no asynchronous video output mux is used.
// Compile hdmi1080_video_system_cdc_reset.v, never the same-named old system.
// Input format, polarity and source sampling edge require separate evidence.
module hdmi_camera_fisheye_top #(
    parameter integer INPUT_TIMING_CONFIGURED=0,
    parameter integer RX_VS_ACTIVE_LEVEL=1,
    parameter integer RX_DE_ACTIVE_LEVEL=1,
    parameter integer CFG_SETTLE_CYCLES=2700000,
    parameter integer PCLK_STALE_REF_CYCLES=2700000
)(
    input clk_27m,clk_p,clk_n,reset_n,key1_n,
    input pixclk_in,vs_in,hs_in,de_in,input [7:0] r_in,g_in,b_in,
    output pix_clk,hs_out,vs_out,de_out,output [7:0] r_out,g_out,b_out,
    inout hd_scl,hd_sda,output rstn_out,output [7:0] led,output uart_tx,
    output mem_rst_n,mem_ck,mem_ck_n,mem_cke,mem_cs_n,mem_ras_n,mem_cas_n,mem_we_n,mem_odt,
    output [14:0] mem_a,output [2:0] mem_ba,
    inout [3:0] mem_dqs,mem_dqs_n,inout [31:0] mem_dq,output [3:0] mem_dm
);
    // Pure compile configuration for the observed 1920x1080 digital timing.
    // The builder selects 1 and measured VS/DE levels for this experiment.
    // This does not accept RGB packing, progressive video, the sampling edge,
    // external AC, optical correctness or any processing/display frame rate.
    localparam TIMING_CONFIG_OK=INPUT_TIMING_CONFIGURED==1 &&
        (RX_VS_ACTIVE_LEVEL==0 || RX_VS_ACTIVE_LEVEL==1) &&
        (RX_DE_ACTIVE_LEVEL==0 || RX_DE_ACTIVE_LEVEL==1) &&
        CFG_SETTLE_CYCLES>=1 && PCLK_STALE_REF_CYCLES>=65536 &&
        PCLK_STALE_REF_CYCLES<=2147483647;

    (* async_reg="true" *) reg [1:0] key_reset_sync=0;
    always @(posedge clk_27m or negedge reset_n)
        if(!reset_n)key_reset_sync<=0;else key_reset_sync<={key_reset_sync[0],1'b1};
    reg [19:0] power_count=0;
    reg power_ready=0;
    always @(posedge clk_27m or negedge reset_n)begin
        if(!reset_n)begin power_count<=0;power_ready<=0;end
        else if(!key_reset_sync[1])begin power_count<=0;power_ready<=0;end
        else if(!(&power_count))power_count<=power_count+1'b1;
        else power_ready<=1;
    end
    wire global_reset_n=reset_n && power_ready;
    assign rstn_out=global_reset_n;

    reg [31:0] cfg_wait_count=0;
    reg cfg_ready=0;
    always @(posedge clk_27m or negedge global_reset_n)begin
        if(!global_reset_n)begin cfg_wait_count<=0;cfg_ready<=0;end
        else if(!cfg_ready)begin
            if(cfg_wait_count<CFG_SETTLE_CYCLES-1)cfg_wait_count<=cfg_wait_count+1'b1;
            else cfg_ready<=1;
        end
    end
    wire cfg_reset_n=global_reset_n && cfg_ready;
    wire cfg_clk,cfg_lock,video_lock;
    cfg_pll configuration_pll(.clkin1(clk_27m),.clkout0(cfg_clk),.lock(cfg_lock));
    // Existing generated PLL: nominal 74.25MHz, independent of input PCLK.
    bringup_pll video_pll(.clkin1(clk_27m),.clkout0(pix_clk),.lock(video_lock));
    wire rx_done,tx_done,cfg_failed;
    wire [3:0] cfg_error;
    wire [31:0] cfg_transactions;
    wire [15:0] cfg_last_address;
    wire [7:0] cfg_last_value;
    wire [1:0] cfg_last_meta;
    // Reuse exactly the RAW candidate's RX rearm, checked TX and IIC driver.
    // Done means transactions completed; it is not evidence of input format.
    ms72xx_rearm_observed_ctl hdmi_configuration(
        .clk(cfg_clk),.rst_n(cfg_reset_n),.init_over_rx(rx_done),.init_over(tx_done),
        .init_failed(cfg_failed),.error_code(cfg_error),.iic_scl(hd_scl),.iic_sda(hd_sda),
        .completed_transactions(cfg_transactions),.last_address(cfg_last_address),
        .last_value(cfg_last_value),.last_meta(cfg_last_meta));

    // Every RGB/control pad has one common PCLK sampling stage. Consumers
    // read these registered values only. No raw-pad counter/enable bypass.
    (* async_reg="true" *) reg [1:0] input_reset=0;
    always @(posedge pixclk_in or negedge global_reset_n)
        if(!global_reset_n)input_reset<=0;else input_reset<={input_reset[0],1'b1};
    wire sampled_vs,sampled_hs,sampled_de,sampled_valid;
    wire [23:0] sampled_rgb;
    wire input_vs_active,input_de_active;
    hdmi_camera_pixel_sampler #(.VS_ACTIVE_LEVEL(RX_VS_ACTIVE_LEVEL),.DE_ACTIVE_LEVEL(RX_DE_ACTIVE_LEVEL)) input_sampler(
        .pclk(pixclk_in),.rst_n(global_reset_n),.raw_vs(vs_in),.raw_hs(hs_in),.raw_de(de_in),
        .raw_rgb({r_in,g_in,b_in}),.sampled_vs(sampled_vs),.sampled_hs(sampled_hs),.sampled_de(sampled_de),
        .sampled_rgb(sampled_rgb),.sampled_valid(sampled_valid),.vs_active(input_vs_active),.de_active(input_de_active));
    // The watchdog source bit clears even if PCLK is stopped. A retained
    // pre-reset 1 must not look like fresh activity in the new reset epoch.
    reg [15:0] pclk_divider;
    always @(posedge pixclk_in or negedge global_reset_n)
        if(!global_reset_n)pclk_divider<=0;
        else if(!input_reset[1])pclk_divider<=0;
        else pclk_divider<=pclk_divider+1'b1;
    // HS is sampled with RGB/VS/DE; capture's existing interface is DE+VS.
    // This sticky activity LED gives sampled HS a real local consumer. It
    // deliberately does not infer polarity, validate video or gate capture.
    reg hs_previous,hs_history_valid,hs_transition_seen;
    always @(posedge pixclk_in)begin
        if(!input_reset[1])begin hs_previous<=0;hs_history_valid<=0;hs_transition_seen<=0;end
        else if(sampled_valid)begin
            hs_previous<=sampled_hs;hs_history_valid<=1;
            if(hs_history_valid && sampled_hs!=hs_previous)hs_transition_seen<=1;
        end
    end

    wire ddr_ref_clk,core_clk,ddr_init_done,ddr_pll_lock;
    wire phy_pll_lock,gpll_lock,rst_gpll_lock,ddrphy_cpd_lock;
    GTP_INBUFGDS #(.IOSTANDARD("DEFAULT"),.TERM_DIFF("ON")) u_gtp(
        .O(ddr_ref_clk),.I(clk_p),.IB(clk_n));
    wire [27:0] awaddr,araddr;
    wire [3:0] awlen,arlen,rid;
    wire awvalid,awready,arvalid,arready,wready,wlast,rvalid,rlast;
    wire [255:0] wdata,rdata;
    wire [31:0] wstrb;
    // Real vendor UI: 4-byte address units, WREADY consumes data, controller
    // returns WLAST, no AXI B channel. Keep every inactive APB/debug tie-off.
    ddr3_test u_ddr3_test_h(
        .ref_clk(ddr_ref_clk),.resetn(global_reset_n),.core_clk(core_clk),.pll_lock(ddr_pll_lock),
        .ddr_init_done(ddr_init_done),.phy_pll_lock(phy_pll_lock),.gpll_lock(gpll_lock),
        .rst_gpll_lock(rst_gpll_lock),.ddrphy_cpd_lock(ddrphy_cpd_lock),
        .axi_awaddr(awaddr),.axi_awuser_ap(1'b0),.axi_awuser_id(4'd0),.axi_awlen(awlen),
        .axi_awready(awready),.axi_awvalid(awvalid),.axi_wdata(wdata),.axi_wstrb(wstrb),
        .axi_wready(wready),.axi_wusero_id(),.axi_wusero_last(wlast),
        .axi_araddr(araddr),.axi_aruser_ap(1'b0),.axi_aruser_id(4'd0),.axi_arlen(arlen),
        .axi_arready(arready),.axi_arvalid(arvalid),.axi_rdata(rdata),.axi_rid(rid),.axi_rlast(rlast),.axi_rvalid(rvalid),
        .apb_clk(1'b0),.apb_rst_n(1'b1),.apb_sel(1'b0),.apb_enable(1'b0),
        .apb_addr(8'd0),.apb_write(1'b0),.apb_ready(),.apb_wdata(16'd0),.apb_rdata(),
        .mem_rst_n(mem_rst_n),.mem_ck(mem_ck),.mem_ck_n(mem_ck_n),.mem_cke(mem_cke),.mem_cs_n(mem_cs_n),
        .mem_ras_n(mem_ras_n),.mem_cas_n(mem_cas_n),.mem_we_n(mem_we_n),.mem_odt(mem_odt),
        .mem_a(mem_a),.mem_ba(mem_ba),.mem_dqs(mem_dqs),.mem_dqs_n(mem_dqs_n),.mem_dq(mem_dq),.mem_dm(mem_dm),
        .dbg_gate_start(1'b0),.dbg_cpd_start(1'b0),.dbg_ddrphy_rst_n(1'b1),.dbg_gpll_scan_rst(1'b0),
        .samp_position_dyn_adj(1'b0),.init_samp_position_even(32'd0),.init_samp_position_odd(32'd0),
        .wrcal_position_dyn_adj(1'b0),.init_wrcal_position(32'd0),.force_read_clk_ctrl(1'b0),
        .init_slip_step(16'd0),.init_read_clk_ctrl(12'd0),
        .debug_calib_ctrl(),.dbg_slice_status(),.dbg_slice_state(),.debug_data(),.dbg_dll_upd_state(),
        .debug_gpll_dps_phase(),.dbg_rst_dps_state(),.dbg_tran_err_rst_cnt(),.dbg_ddrphy_init_fail(),
        .debug_cpd_offset_adj(1'b0),.debug_cpd_offset_dir(1'b0),.debug_cpd_offset(10'd0),
        .debug_dps_cnt_dir0(),.debug_dps_cnt_dir1(),.ck_dly_en(1'b0),.init_ck_dly_step(8'd0),
        .ck_dly_set_bin(),.align_error(),.debug_rst_state(),.debug_cpd_state());

    wire system_failed;
    wire [7:0] system_fault;
    wire [31:0] captured_frames,processed_frames,presented_frames,underflows,mismatches;
    wire [31:0] last_process_cycles,cache_hits,cache_misses,cache_queries;
    wire [31:0] scan_good_frames,scan_repeat_frames,scan_blank_frames;
    (* async_reg="true" *) reg [1:0] ref_reset=0;
    always @(posedge clk_27m or negedge global_reset_n)
        if(!global_reset_n)ref_reset<=0;else ref_reset<={ref_reset[0],1'b1};
    (* async_reg="true" *) reg [1:0] cfg_lock_ref,video_lock_ref,rx_done_ref,tx_done_ref,cfg_failed_ref;
    (* async_reg="true" *) reg [1:0] ddr_init_ref,ddr_pll_ref,system_failed_ref,processed_ref;
    (* async_reg="true" *) reg [1:0] pclk_activity_ref,hs_activity_ref;
    always @(posedge clk_27m or negedge global_reset_n)begin
        if(!global_reset_n)begin
            cfg_lock_ref<=0;video_lock_ref<=0;rx_done_ref<=0;tx_done_ref<=0;cfg_failed_ref<=0;
            ddr_init_ref<=0;ddr_pll_ref<=0;system_failed_ref<=0;processed_ref<=0;
            pclk_activity_ref<=0;hs_activity_ref<=0;
        end else if(!ref_reset[1])begin
            cfg_lock_ref<=0;video_lock_ref<=0;rx_done_ref<=0;tx_done_ref<=0;cfg_failed_ref<=0;
            ddr_init_ref<=0;ddr_pll_ref<=0;system_failed_ref<=0;processed_ref<=0;
            pclk_activity_ref<=0;hs_activity_ref<=0;
        end else begin
            cfg_lock_ref<={cfg_lock_ref[0],cfg_lock};video_lock_ref<={video_lock_ref[0],video_lock};
            rx_done_ref<={rx_done_ref[0],rx_done};tx_done_ref<={tx_done_ref[0],tx_done};
            cfg_failed_ref<={cfg_failed_ref[0],cfg_failed};
            ddr_init_ref<={ddr_init_ref[0],ddr_init_done};ddr_pll_ref<={ddr_pll_ref[0],ddr_pll_lock};
            system_failed_ref<={system_failed_ref[0],system_failed};processed_ref<={processed_ref[0],processed_frames[4]};
            pclk_activity_ref<={pclk_activity_ref[0],pclk_divider[15]};
            hs_activity_ref<={hs_activity_ref[0],hs_transition_seen && sampled_valid};
        end
    end
    wire ddr_ready_ref=ddr_init_ref[1] && ddr_pll_ref[1];
    reg pclk_activity_seen,pclk_observed;
    reg [31:0] pclk_age;
    always @(posedge clk_27m or negedge global_reset_n)begin
        if(!global_reset_n)begin pclk_activity_seen<=0;pclk_observed<=0;pclk_age<=0;end
        else if(!ref_reset[1])begin pclk_activity_seen<=0;pclk_observed<=0;pclk_age<=0;end
        else if(pclk_activity_ref[1]!=pclk_activity_seen)begin
            pclk_activity_seen<=pclk_activity_ref[1];pclk_observed<=1;pclk_age<=0;
        end else if(pclk_age<PCLK_STALE_REF_CYCLES)pclk_age<=pclk_age+1'b1;
    end
    // Timeout watches only source-clock presence. It is not a VS/DE/frame
    // progress watchdog and never releases a bank or resets a transaction.
    wire pclk_stale=pclk_age>=PCLK_STALE_REF_CYCLES;
    reg pipeline_release=0,board_failed=0;
    reg [7:0] board_fault=0;
    reg [23:0] heart_count=0;
    reg heartbeat=0;
    always @(posedge clk_27m or negedge global_reset_n)begin
        if(!global_reset_n)begin pipeline_release<=0;board_failed<=0;board_fault<=0;heart_count<=0;heartbeat<=0;end
        else if(!ref_reset[1])begin pipeline_release<=0;board_failed<=0;board_fault<=0;heart_count<=0;heartbeat<=0;end
        else begin
            if(heart_count==13499999)begin heart_count<=0;heartbeat<=!heartbeat;end
            else heart_count<=heart_count+1'b1;
            if(!pipeline_release && !board_failed && TIMING_CONFIG_OK && !cfg_failed_ref[1] &&
                cfg_lock_ref[1] && video_lock_ref[1] && rx_done_ref[1] && tx_done_ref[1] &&
                ddr_ready_ref && pclk_observed && !pclk_stale)pipeline_release<=1;
            if(!board_failed && cfg_failed_ref[1])begin board_failed<=1;board_fault<=8'ha7;end
            else if(pipeline_release && !board_failed)begin
                if(pclk_stale)begin board_failed<=1;board_fault<=8'ha1;end
                else if(!ddr_ready_ref)begin board_failed<=1;board_fault<=8'ha3;end
                else if(!cfg_lock_ref[1] || !video_lock_ref[1])begin board_failed<=1;board_fault<=8'ha4;end
                else if(!rx_done_ref[1] || !tx_done_ref[1])begin board_failed<=1;board_fault<=8'ha5;end
                else if(system_failed_ref[1])begin board_failed<=1;board_fault<=8'ha6;end
            end
        end
    end
    // The one startup release is monotonic. Only common manual/power reset
    // resets DDR and this whole epoch; runtime faults stop admission instead.
    wire pipeline_reset_n=global_reset_n && pipeline_release;
    (* async_reg="true" *) reg [1:0] core_reset=0,board_failed_core=0;
    always @(posedge core_clk or negedge pipeline_reset_n)
        if(!pipeline_reset_n)begin core_reset<=0;board_failed_core<=0;end
        else begin core_reset<={core_reset[0],1'b1};board_failed_core<={board_failed_core[0],board_failed};end

    // Reuse the proven KEY1 control in the DDR core domain. It starts in
    // corrected mode, qualifies both release and press for 20 ms, and emits
    // one change for a held key. The mapper accepts the requested mode only
    // at its frame handshake after all prior coordinate requests drain.
    wire corrected_requested,view_toggle_pulse;
    camera720_view_control #(.DEBOUNCE_CYCLES(2500000)) view_control(
        .clk(core_clk),.rst_n(core_reset[1]),.key1_n(key1_n),
        .corrected_requested(corrected_requested),.toggle_pulse(view_toggle_pulse));
    (* async_reg="true" *) reg [1:0] corrected_requested_ref=0;
    always @(posedge clk_27m or negedge global_reset_n)
        if(!global_reset_n)corrected_requested_ref<=0;
        else if(!ref_reset[1])corrected_requested_ref<=0;
        else corrected_requested_ref<={corrected_requested_ref[0],corrected_requested};

    // Retain every raw RGB pad as a real color input. Quantization and timing
    // have the same two-cycle PCLK delay before the unchanged RGB565 DMA.
    wire quantized_valid,quantized_vs,quantized_de;
    wire [23:0] quantized_rgb;
    hdmi_camera_rgb565_quantizer input_quantizer(
        .clk(pixclk_in),.rst_n(input_reset[1]),.in_valid(sampled_valid),
        .in_vs(input_vs_active),.in_de(input_de_active),.in_rgb(sampled_rgb),
        .out_valid(quantized_valid),.out_vs(quantized_vs),.out_de(quantized_de),.out_rgb(quantized_rgb));
    wire [23:0] pixel_rgb;
    wire display_valid;
    hdmi_camera_fisheye_system #(.WIDTH(1920),.HEIGHT(1080),.BANK_STRIDE(1048576),
        .HT(2200),.VT(1125),.HS(44),.VS(5),.X0(192),.Y0(41)) system(
        .core_clk(core_clk),.pix_in_clk(pixclk_in),.pix_out_clk(pix_clk),.rst_n(pipeline_reset_n),
        .capture_admit(core_reset[1] && !board_failed_core[1]),
        .scan_enable(core_reset[1] && !board_failed_core[1]),
        .external_fault(board_failed_core[1]),.external_fault_code(board_fault),
        .pix_in_vsync_active(quantized_vs && quantized_valid),.pix_in_de(quantized_de && quantized_valid),.pix_in_rgb(quantized_rgb),
        .cfg_corrected(corrected_requested),
        .awaddr(awaddr),.araddr(araddr),.awlen(awlen),.arlen(arlen),.awvalid(awvalid),.arvalid(arvalid),
        .awready(awready),.arready(arready),.wdata(wdata),.wstrb(wstrb),.wready(wready),.wlast(wlast),
        .rdata(rdata),.rvalid(rvalid),.rlast(rlast),.rid(rid),
        .pix_hs(hs_out),.pix_vs(vs_out),.pix_de(de_out),.pix_rgb(pixel_rgb),.display_valid(display_valid),
        .failed(system_failed),.fault(system_fault),.captured_frames(captured_frames),
        .processed_frames(processed_frames),.presented_frames(presented_frames),.underflows(underflows),.mismatches(mismatches),
        .last_process_cycles(last_process_cycles),.cache_hits(cache_hits),.cache_misses(cache_misses),.queries(cache_queries),
        .scan_good_frames(scan_good_frames),.scan_repeat_frames(scan_repeat_frames),.scan_blank_frames(scan_blank_frames));
    // Single-bit timing levels cross through 2FF synchronizers. Frame edge
    // counters and all processing counters are then sampled in core_clk.
    (* async_reg="true" *) reg [1:0] input_vs_core=0,output_vs_core=0;
    reg input_vs_seen,output_vs_seen;
    reg [31:0] source_frames,scan_refreshes;
    always @(posedge core_clk)begin
        if(!core_reset[1])begin
            input_vs_core<=0;output_vs_core<=0;input_vs_seen<=0;output_vs_seen<=0;
            source_frames<=0;scan_refreshes<=0;
        end else begin
            input_vs_core<={input_vs_core[0],input_vs_active};
            output_vs_core<={output_vs_core[0],vs_out};
            input_vs_seen<=input_vs_core[1];output_vs_seen<=output_vs_core[1];
            if(input_vs_core[1] && !input_vs_seen)source_frames<=source_frames+1'b1;
            if(output_vs_core[1] && !output_vs_seen)scan_refreshes<=scan_refreshes+1'b1;
        end
    end
    // Profile ID is updated from the generated calibration profile before
    // this new candidate is frozen. It is not the old OV5640 lens profile.
    hdmi_camera_fisheye_status_uart #(.CLOCK_HZ(125000000),.BAUD(115200),
        .BUILD_ID(32'h11030001),.PROFILE_ID(64'hed59f83e3cfbc77b)) status_uart(
        .clk(core_clk),.rst_n(core_reset[1]),.source_accepted(captured_frames),
        .processed(processed_frames),.unique_presented(presented_frames),
        .source_frames(source_frames),.scan_refreshes(scan_refreshes),.last_process_cycles(last_process_cycles),
        .cache_hits(cache_hits),.cache_misses(cache_misses),.queries(cache_queries),
        .scan_good(scan_good_frames),.scan_repeat(scan_repeat_frames),.scan_blank(scan_blank_frames),
        .corrected_requested(corrected_requested),.status_valid(core_reset[1]),
        .failed(system_failed || board_failed_core[1]),
        .fault(system_failed ? system_fault:board_fault),.tx(uart_tx));
    assign {r_out,g_out,b_out}=pixel_rgb;
    // LED6 indicates the requested mode; completed frames switch at scan boundaries.
    assign led={board_failed || system_failed_ref[1],corrected_requested_ref[1],pipeline_release,hs_activity_ref[1],
        tx_done_ref[1],rx_done_ref[1],ddr_ready_ref,heartbeat};
endmodule
