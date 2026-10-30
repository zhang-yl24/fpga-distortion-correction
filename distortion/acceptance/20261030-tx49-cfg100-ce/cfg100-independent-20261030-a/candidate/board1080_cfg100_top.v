`timescale 1ns/1ps
// Independent DEVELOPMENT board entry. Native1080 RGB interpretation follows
// the board reference, but MS7200 lock/register readback/edge timing, actual
// source, routed CDC/STA/resources and optical calibration are NOT accepted.
// Runtime faults STOP ADMISSIONS and ask the system to drain; they NEVER
// locally reset a FIFO or withdraw an already-issued DDR AW transaction.
module board1080_top(
    input clk_27m,clk_p,clk_n,reset_n,
    input pixclk_in,vs_in,hs_in,de_in,input [7:0] r_in,g_in,b_in,
    output pix_clk,hs_out,vs_out,de_out,output [7:0] r_out,g_out,b_out,
    output hd_scl,inout hd_sda,output rstn_out,output [7:0] led,
    output mem_rst_n,mem_ck,mem_ck_n,mem_cke,mem_cs_n,mem_ras_n,mem_cas_n,mem_we_n,mem_odt,
    output [14:0] mem_a,output [2:0] mem_ba,
    inout [3:0] mem_dqs,mem_dqs_n,inout [31:0] mem_dq,output [3:0] mem_dm
);
    (* async_reg="true" *) reg [1:0] key_reset_sync=0;
    always @(posedge clk_27m or negedge reset_n)
        if(!reset_n)key_reset_sync<=0;else key_reset_sync<={key_reset_sync[0],1'b1};
    reg [19:0] power_count=0;
    always @(posedge clk_27m)
        if(!key_reset_sync[1])power_count<=0;else if(!(&power_count))power_count<=power_count+1'b1;
    // DERIVED reset candidate: register the terminal count. A binary counter
    // reduction must not directly deassert the shared asynchronous reset tree.
    reg power_ready=0;
    always @(posedge clk_27m or negedge reset_n)
        if(!reset_n)power_ready<=0;
        else if(!key_reset_sync[1])power_ready<=0;
        else if(&power_count)power_ready<=1;
    wire global_reset_n=reset_n && power_ready;
    assign rstn_out=global_reset_n;
    wire cfg_clk,cfg_lock,video_lock;
    // Unmodified generated IPs: cfg_pll is nominal10MHz (matches the vendor
    // IIC driver's CLK_FRE); bringup_pll is nominal74.25MHz, not148.5MHz.
    cfg_pll configuration_pll(.clkin1(clk_27m),.clkout0(cfg_clk),.lock(cfg_lock));
    bringup_pll video_pll(.clkin1(clk_27m),.clkout0(pix_clk),.lock(video_lock));
    wire rx_init_done,tx_init_done;
    wire cfg_configuration_reset_n;
    cfg100_startup_hold #(.SETTLE_CYCLES(1000000)) configuration_hold(
        .cfg_clk(cfg_clk),.chip_reset_n(global_reset_n),.cfg_locked(cfg_lock),
        .cfg_reset_n(cfg_configuration_reset_n));
    ms72xx_cfg100_ctl hdmi_configuration(.clk(cfg_clk),.rst_n(cfg_configuration_reset_n),
        .init_over_rx(rx_init_done),.init_over(tx_init_done),.iic_scl(hd_scl),.iic_sda(hd_sda));
    // init_over only means the reference sequencer completed. It is not an
    // HDMI PHY lock or a readback proof of RGB888/SDR edge configuration.

    wire ddr_ref_clk,core_clk,ddr_init_done,ddr_pll_lock;
    wire phy_pll_lock,gpll_lock,rst_gpll_lock,ddrphy_cpd_lock;
    GTP_INBUFGDS #(.IOSTANDARD("DEFAULT"),.TERM_DIFF("ON")) u_gtp(
        .O(ddr_ref_clk),.I(clk_p),.IB(clk_n));
    wire [27:0] awaddr,araddr;wire [3:0] awlen,arlen,rid;
    wire awvalid,awready,arvalid,arready,wready,wlast,rvalid,rlast;
    wire [255:0] wdata,rdata;wire [31:0] wstrb;
    ddr3_test u_ddr3_test_h(
        .ref_clk(ddr_ref_clk),.resetn(global_reset_n),.core_clk(core_clk),.pll_lock(ddr_pll_lock),
        .ddr_init_done(ddr_init_done),.phy_pll_lock(phy_pll_lock),.gpll_lock(gpll_lock),
        .rst_gpll_lock(rst_gpll_lock),.ddrphy_cpd_lock(ddrphy_cpd_lock),
        .axi_awaddr(awaddr),.axi_awuser_ap(1'b0),.axi_awuser_id(4'd0),.axi_awlen(awlen),
        .axi_awready(awready),.axi_awvalid(awvalid),.axi_wdata(wdata),.axi_wstrb(wstrb),
        .axi_wready(wready),.axi_wusero_id(),.axi_wusero_last(wlast),
        .axi_araddr(araddr),.axi_aruser_ap(1'b0),.axi_aruser_id(4'd0),.axi_arlen(arlen),
        .axi_arready(arready),.axi_arvalid(arvalid),.axi_rdata(rdata),.axi_rid(rid),.axi_rlast(rlast),.axi_rvalid(rvalid),
        // Exact inactive APB tie-offs from the signed board baseline. Do not
        //leave real controller configuration inputs floating in this entry.
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

    (* async_reg="true" *) reg [1:0] ref_reset=0;
    always @(posedge clk_27m or negedge global_reset_n)
        if(!global_reset_n)ref_reset<=0;else ref_reset<={ref_reset[0],1'b1};
    (* async_reg="true" *) reg [1:0] cfg_lock_ref,video_lock_ref,rx_done_ref,tx_done_ref,ddr_ready_ref;
    (* async_reg="true" *) reg [1:0] system_failed_ref,processed_bit_ref;
    wire system_failed;wire [7:0] system_fault;
    wire [31:0] captured_frames,processed_frames,presented_frames,underflows;
    always @(posedge clk_27m or negedge global_reset_n)begin
        if(!global_reset_n)begin
            cfg_lock_ref<=0;video_lock_ref<=0;rx_done_ref<=0;tx_done_ref<=0;ddr_ready_ref<=0;
            system_failed_ref<=0;processed_bit_ref<=0;
        end else if(!ref_reset[1])begin
            cfg_lock_ref<=0;video_lock_ref<=0;rx_done_ref<=0;tx_done_ref<=0;ddr_ready_ref<=0;
            system_failed_ref<=0;processed_bit_ref<=0;
        end else begin
            cfg_lock_ref<={cfg_lock_ref[0],cfg_lock};video_lock_ref<={video_lock_ref[0],video_lock};
            rx_done_ref<={rx_done_ref[0],rx_init_done};tx_done_ref<={tx_done_ref[0],tx_init_done};
            ddr_ready_ref<={ddr_ready_ref[0],ddr_init_done && ddr_pll_lock};
            system_failed_ref<={system_failed_ref[0],system_failed};processed_bit_ref<={processed_bit_ref[0],processed_frames[4]};
        end
    end
    wire normalized_vs,input_qualified,input_failed,input_polarity,vs_inactive,hs_inactive;
    wire [7:0] input_fault;
    wire [31:0] monitor_good_frames,monitor_bad_frames,monitor_pclk_edges;
    wire [15:0] monitor_pixels,monitor_lines;
    // Only the observer can be held/restarted during chip initialization. The
    // real system/FIFO reset below is a separate once-released global latch.
    wire observer_reset_n=global_reset_n && rx_done_ref[1];
    hdmi1080_input_status input_status(.ref_clk(clk_27m),.pix_clk(pixclk_in),.rst_n(observer_reset_n),
        .pix_vs(vs_in),.pix_hs(hs_in),.pix_de(de_in),.normalized_vs(normalized_vs),
        .qualified(input_qualified),.failed(input_failed),.fault(input_fault),
        .polarity_known_ref(input_polarity),.vs_inactive_ref(vs_inactive),.hs_inactive_ref(hs_inactive),
        .good_frames(monitor_good_frames),.bad_frames(monitor_bad_frames),.pclk_edges_per_window(monitor_pclk_edges),
        .last_pixels_per_line(monitor_pixels),.last_lines(monitor_lines));
    reg pipeline_release=0,board_failed=0;reg [7:0] board_fault=0;
    reg [23:0] heartbeat_count=0;reg heartbeat=0;
    always @(posedge clk_27m or negedge global_reset_n)begin
        if(!global_reset_n)begin pipeline_release<=0;board_failed<=0;board_fault<=0;heartbeat_count<=0;heartbeat<=0;end
        else if(!ref_reset[1])begin pipeline_release<=0;board_failed<=0;board_fault<=0;heartbeat_count<=0;heartbeat<=0;end
        else begin
            if(heartbeat_count==13499999)begin heartbeat_count<=0;heartbeat<=!heartbeat;end
            else heartbeat_count<=heartbeat_count+1'b1;
            if(!pipeline_release && !board_failed && cfg_lock_ref[1] && video_lock_ref[1] &&
                rx_done_ref[1] && tx_done_ref[1] && ddr_ready_ref[1] && input_qualified)pipeline_release<=1;
            if(pipeline_release && !board_failed)begin
                if(input_failed)begin board_failed<=1;board_fault<=8'ha1;end
                else if(!input_qualified)begin board_failed<=1;board_fault<=8'ha2;end
                else if(!ddr_ready_ref[1])begin board_failed<=1;board_fault<=8'ha3;end
                else if(!cfg_lock_ref[1] || !video_lock_ref[1])begin board_failed<=1;board_fault<=8'ha4;end
                else if(!rx_done_ref[1] || !tx_done_ref[1])begin board_failed<=1;board_fault<=8'ha5;end
                else if(system_failed_ref[1])begin board_failed<=1;board_fault<=8'ha6;end
            end
        end
    end
    // pipeline_release is monotonic until common manual/power reset. A
    // runtime fault must never silently restart bank ownership or drop AWVALID.
    wire pipeline_reset_n=global_reset_n && pipeline_release;
    (* async_reg="true" *) reg [1:0] core_reset=0,qualified_core=0,board_failed_core=0;
    always @(posedge core_clk or negedge pipeline_reset_n)begin
        if(!pipeline_reset_n)begin core_reset<=0;qualified_core<=0;board_failed_core<=0;end
        else begin
            core_reset<={core_reset[0],1'b1};qualified_core<={qualified_core[0],input_qualified};
            board_failed_core<={board_failed_core[0],board_failed};
        end
    end
    // board_fault changes only on first sticky board_failed and is held for
    // the remainder of this common-reset epoch; the synchronized predicate
    // reaches the consumer after the held code has settled.
    `include "D:/English/FPGA/distortion/build/offline-20261024/boardtop-penn-prep-20261029-a/board1080-penn.vh"
    wire correction_enable,system_source_commit;
    // The actual bank commit snapshots the old mode; its registered
    // public source_commit toggles the selector at the next core edge.
    // All control is core-domain; failure holds mode and preserves drain.
    frame_ab_control frame_mode_control(.clk(core_clk),.rst_n(core_reset[1]),
        .commit_pulse(system_source_commit),.failed(system_failed || board_failed_core[1]),
        .correction_enable(correction_enable));
    wire [23:0] pixel_rgb;
    hdmi1080_video_system_geometry_ab #(.WIDTH(1920),.HEIGHT(1080),.BANK_STRIDE(1048576),
        .MAX_RADIUS_Q22(B1080_RADIUS_Q22),.HT(2200),.VT(1125),.HS(44),.VS(5),.X0(192),.Y0(41)) system(
        .core_clk(core_clk),.pix_in_clk(pixclk_in),.pix_out_clk(pix_clk),.rst_n(pipeline_reset_n),
        .gamma_enable(B1080_GAMMA_ENABLE),.correction_enable(correction_enable),
        .cfg_rot_cx(B1080_ROT_CX),.cfg_rot_cy(B1080_ROT_CY),
        .cfg_rot_cos(B1080_ROT_COS),.cfg_rot_sin(B1080_ROT_SIN),
        .source_commit(system_source_commit),
        .capture_admit(core_reset[1] && qualified_core[1] && !board_failed_core[1]),
        .scan_enable(core_reset[1] && !board_failed_core[1]),
        .external_fault(board_failed_core[1]),.external_fault_code(board_fault),
        .pix_in_vsync_active(normalized_vs),.pix_in_de(de_in),.pix_in_rgb({r_in,g_in,b_in}),
        .cfg_out_cx(B1080_OUT_CX),.cfg_out_cy(B1080_OUT_CY),.cfg_src_cx(B1080_SRC_CX),.cfg_src_cy(B1080_SRC_CY),
        .cfg_src_fx(B1080_SRC_FX),.cfg_src_fy(B1080_SRC_FY),.cfg_inv_fx(B1080_INV_FX),.cfg_inv_fy(B1080_INV_FY),
        .cfg_k1(B1080_K1),.cfg_k2(B1080_K2),.cfg_k3(B1080_K3),.cfg_p1(B1080_P1),.cfg_p2(B1080_P2),
        .awaddr(awaddr),.araddr(araddr),.awlen(awlen),.arlen(arlen),.awvalid(awvalid),.arvalid(arvalid),
        .awready(awready),.arready(arready),.wdata(wdata),.wstrb(wstrb),.wready(wready),.wlast(wlast),
        .rdata(rdata),.rvalid(rvalid),.rlast(rlast),.rid(rid),
        .pix_hs(hs_out),.pix_vs(vs_out),.pix_de(de_out),.pix_rgb(pixel_rgb),
        .failed(system_failed),.fault(system_fault),.captured_frames(captured_frames),
        .processed_frames(processed_frames),.presented_frames(presented_frames),.underflows(underflows));
    assign {r_out,g_out,b_out}=pixel_rgb;
    assign led={board_failed || system_failed_ref[1],processed_bit_ref[1],pipeline_release,input_qualified,
        tx_done_ref[1],rx_done_ref[1],ddr_ready_ref[1],heartbeat};
endmodule
