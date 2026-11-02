// Independent 720p transport candidate. New physical and board verification required.
`timescale 1ns/1ps
// CAM2 1280x720 input -> existing DDR/remap/output implementation.
// Camera image is centered in the existing 1080p30 HDMI raster.
// Exact identity mapping, no rotation, gamma bypass. Not lens correction.
// This top requires its own physical verification and bitstream.
module camera720_calibrated_stats_delay_top #(
    parameter CAMERA_WARMUP_MS=8000
)(
    input clk_27m,clk_p,clk_n,reset_n,
    output uart_txd,
    input cam_pclk,cam_vsync,cam_href,input [7:0] cam_data,
    inout cam_rst_n,cam_scl,cam_sda,
    output pix_clk,hs_out,vs_out,de_out,output [7:0] r_out,g_out,b_out,
    inout hd_scl,hd_sda,output rstn_out,output [7:0] led,
    output mem_rst_n,mem_ck,mem_ck_n,mem_cke,mem_cs_n,mem_ras_n,mem_cas_n,mem_we_n,mem_odt,
    output [14:0] mem_a,output [2:0] mem_ba,
    inout [3:0] mem_dqs,mem_dqs_n,inout [31:0] mem_dq,output [3:0] mem_dm
);
    localparam WIDTH=1280,HEIGHT=720,HT=2200,VT=1125,HS=44,VS=5,X0=192,Y0=41,
        OUTPUT_WIDTH=1920,OUTPUT_HEIGHT=1080;
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
    wire video_lock;
    bringup_pll video_pll(.clkin1(clk_27m),.clkout0(pix_clk),.lock(video_lock));
    wire tx_init_done;wire [3:0] tx_init_error;
    // Real independent controller retains its 27MHz startup/delay/retry counts.
    // ready means configuration completed, not a physical HDMI lock proof.
    hdmi_tx_init hdmi_configuration(.clk(clk_27m),.rst_n(global_reset_n),
        .hd_scl(hd_scl),.hd_sda(hd_sda),.ready(tx_init_done),.error(tx_init_error));

    wire camera_ready,camera_failed,camera_configured;
    wire [7:0] camera_fault;
    // Observe complete DVP frames before releasing capture. The camera monitor
    // has its own reset; loss of authorization only stops new pipeline work.
    ov5640_current720_frontend camera_configuration(
        .ref_clk(clk_27m),.pclk(cam_pclk),.rst_n(global_reset_n),
        .vsync_active(!delayed_cam_vsync),.href_active(!delayed_cam_href),
        .cam_rst_n(cam_rst_n),.cam_scl(cam_scl),.cam_sda(cam_sda),
        .configured(camera_configured),.raw_authorize(camera_ready),
        .failed(camera_failed),.fault(camera_fault));

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
    (* async_reg="true" *) reg [1:0] video_lock_ref=0,ddr_ready_ref=0;
    (* async_reg="true" *) reg [1:0] system_failed_ref=0,processed_bit_ref=0,captured_bit_ref=0;
    wire system_failed;wire [7:0] system_fault;
    wire [31:0] captured_frames,processed_frames,presented_frames,underflows;
    always @(posedge clk_27m or negedge global_reset_n)begin
        if(!global_reset_n)begin
            video_lock_ref<=0;ddr_ready_ref<=0;system_failed_ref<=0;processed_bit_ref<=0;captured_bit_ref<=0;
        end else if(!ref_reset[1])begin
            video_lock_ref<=0;ddr_ready_ref<=0;system_failed_ref<=0;processed_bit_ref<=0;captured_bit_ref<=0;
        end else begin
            video_lock_ref<={video_lock_ref[0],video_lock};
            ddr_ready_ref<={ddr_ready_ref[0],ddr_init_done && ddr_pll_lock};
            system_failed_ref<={system_failed_ref[0],system_failed};
            processed_bit_ref<={processed_bit_ref[0],processed_frames[4]};
            captured_bit_ref<={captured_bit_ref[0],captured_frames[4]};
        end
    end
    wire sensor_armed;
    capture_warmup #(.CLOCK_HZ(27000000),.DELAY_MS(CAMERA_WARMUP_MS)) sensor_warmup(
        .clk(clk_27m),.rst_n(global_reset_n && ref_reset[1]),
        .ready(camera_ready && !camera_failed && video_lock_ref[1] && ddr_ready_ref[1] && tx_init_done),
        .armed(sensor_armed));
    reg pipeline_release=0,board_failed=0;reg [7:0] board_fault=0;
    reg [23:0] heartbeat_count=0;reg heartbeat=0;
    always @(posedge clk_27m or negedge global_reset_n)begin
        if(!global_reset_n)begin
            pipeline_release<=0;board_failed<=0;board_fault<=0;heartbeat_count<=0;heartbeat<=0;
        end else if(!ref_reset[1])begin
            pipeline_release<=0;board_failed<=0;board_fault<=0;heartbeat_count<=0;heartbeat<=0;
        end else begin
            if(heartbeat_count==13499999)begin heartbeat_count<=0;heartbeat<=!heartbeat;end
            else heartbeat_count<=heartbeat_count+1'b1;
            if(!board_failed)begin
                // Error wins simultaneous readiness, including before startup.
                // Sticky fault preserves evidence until a common manual reset.
                if(camera_failed)begin board_failed<=1;board_fault<=8'ha8;end
                else if(|tx_init_error)begin board_failed<=1;board_fault<=8'ha7;end
                else if(pipeline_release)begin
                    if(!camera_ready)begin board_failed<=1;board_fault<=8'ha9;end
                    else if(!ddr_ready_ref[1])begin board_failed<=1;board_fault<=8'ha3;end
                    else if(!video_lock_ref[1])begin board_failed<=1;board_fault<=8'ha4;end
                    else if(!tx_init_done)begin board_failed<=1;board_fault<=8'ha5;end
                    else if(system_failed_ref[1])begin board_failed<=1;board_fault<=8'ha6;end
                end else if(sensor_armed)
                    pipeline_release<=1;
            end
        end
    end
    // Once released, keep the common reset high across runtime faults. Never
    // truncate accepted DDR transactions or silently reset FIFO/bank epochs.
    wire pipeline_reset_n=global_reset_n && pipeline_release;
    (* async_reg="true" *) reg [1:0] core_reset=0,board_failed_core=0;
    always @(posedge core_clk or negedge pipeline_reset_n)begin
        if(!pipeline_reset_n)begin core_reset<=0;board_failed_core<=0;end
        else begin
            core_reset<={core_reset[0],1'b1};
            board_failed_core<={board_failed_core[0],board_failed};
        end
    end
    // Sensor raster remains external and free-running through runtime faults.
    // Only new admissions stop; no local clock-stop reset or lease reclaim.
    `include "board/camera720-current-lens.vh"
    wire [7:0] delayed_cam_data;
    raw_camera_input_delay camera_data_delay(.pad_data(cam_data),.capture_data(delayed_cam_data));
    wire delayed_cam_href, delayed_cam_vsync;
    raw_camera_control_input_delay camera_control_delay(
        .pad_href(cam_href),.pad_vsync(cam_vsync),
        .capture_href(delayed_cam_href),.capture_vsync(delayed_cam_vsync));
    wire [23:0] pixel_rgb;
    camera_vga_video_system #(.WIDTH(WIDTH),.HEIGHT(HEIGHT),.BANK_STRIDE(1048576),
        .OUTPUT_WIDTH(OUTPUT_WIDTH),.OUTPUT_HEIGHT(OUTPUT_HEIGHT),
        .VSYNC_ACTIVE_HIGH(0),.HREF_ACTIVE_HIGH(0),.HIGH_BYTE_FIRST(0),
        .MAX_RADIUS_Q22(C720_RADIUS_Q22),.HT(HT),.VT(VT),.HS(HS),.VS(VS),.X0(X0),.Y0(Y0)) system(
        .core_clk(core_clk),.cam_clk(cam_pclk),.pix_out_clk(pix_clk),.rst_n(pipeline_reset_n),
        .capture_admit(core_reset[1] && !board_failed_core[1]),
        .scan_enable(core_reset[1] && !board_failed_core[1]),
        .external_fault(board_failed_core[1]),.external_fault_code(board_fault),
        .cam_vsync(delayed_cam_vsync),.cam_href(delayed_cam_href),.cam_data(delayed_cam_data),
        .cfg_out_cx(C720_OUT_CX),.cfg_out_cy(C720_OUT_CY),.cfg_src_cx(C720_SRC_CX),.cfg_src_cy(C720_SRC_CY),
        .cfg_src_fx(C720_SRC_FX),.cfg_src_fy(C720_SRC_FY),.cfg_inv_fx(C720_INV_FX),.cfg_inv_fy(C720_INV_FY),
        .cfg_k1(C720_K1),.cfg_k2(C720_K2),.cfg_k3(C720_K3),.cfg_p1(C720_P1),.cfg_p2(C720_P2),
        .awaddr(awaddr),.araddr(araddr),.awlen(awlen),.arlen(arlen),.awvalid(awvalid),.arvalid(arvalid),
        .awready(awready),.arready(arready),.wdata(wdata),.wstrb(wstrb),.wready(wready),.wlast(wlast),
        .rdata(rdata),.rvalid(rvalid),.rlast(rlast),.rid(rid),
        .pix_hs(hs_out),.pix_vs(vs_out),.pix_de(de_out),.pix_rgb(pixel_rgb),
        .failed(system_failed),.fault(system_fault),.captured_frames(captured_frames),
        .processed_frames(processed_frames),.presented_frames(presented_frames),.underflows(underflows));
    assign {r_out,g_out,b_out}=pixel_rgb;
    assign led={board_failed || system_failed_ref[1],processed_bit_ref[1],captured_bit_ref[1],tx_init_done,
        camera_ready,video_lock_ref[1],ddr_ready_ref[1],heartbeat};
    // Read-only observations of existing core-domain counters. No feedback.
    // Existing local reset release is reused; status/underflows are unavailable.
    camera720_core_stats_uart #(.CLOCK_HZ(125000000),.BAUD(115200),
        .SAMPLE_CYCLES(125000000),.BUILD_ID(64'he396af749d6e350d),
        .PROFILE_ID(64'hf79c44d9bdeb5b11)) core_statistics(
        .clk(core_clk),.rst_n(core_reset[1]),
        .source_accepted(captured_frames),.processed(processed_frames),
        .unique_presented(presented_frames),
        .status_valid(1'b0),.failed(1'b0),.fault(8'b0),.tx(uart_txd));

endmodule
