`timescale 1ns/1ps
// Independent processing/output development candidate. Source is an on-chip
// diagnostic image, NOT the connected camera. No HDMI RX pins/controller.
// New top requires its own physical verification; old ADF timing is not reused.
module processed_output_top #(
    parameter WIDTH=1920,HEIGHT=1080,HT=2200,VT=1125,HS=44,VS=5,X0=192,Y0=41
)(
    input clk_27m,clk_p,clk_n,reset_n,
    output pix_clk,hs_out,vs_out,de_out,output [7:0] r_out,g_out,b_out,
    inout hd_scl,hd_sda,output rstn_out,output [7:0] led,
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
    wire video_lock;
    bringup_pll video_pll(.clkin1(clk_27m),.clkout0(pix_clk),.lock(video_lock));
    wire tx_init_done;wire [3:0] tx_init_error;
    // Real independent controller retains its 27MHz startup/delay/retry counts.
    // ready means configuration completed, not a physical HDMI lock proof.
    hdmi_tx_init hdmi_configuration(.clk(clk_27m),.rst_n(global_reset_n),
        .hd_scl(hd_scl),.hd_sda(hd_sda),.ready(tx_init_done),.error(tx_init_error));

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
    (* async_reg="true" *) reg [1:0] system_failed_ref=0,processed_bit_ref=0;
    wire system_failed;wire [7:0] system_fault;
    wire [31:0] captured_frames,processed_frames,presented_frames,underflows;
    always @(posedge clk_27m or negedge global_reset_n)begin
        if(!global_reset_n)begin
            video_lock_ref<=0;ddr_ready_ref<=0;system_failed_ref<=0;processed_bit_ref<=0;
        end else if(!ref_reset[1])begin
            video_lock_ref<=0;ddr_ready_ref<=0;system_failed_ref<=0;processed_bit_ref<=0;
        end else begin
            video_lock_ref<={video_lock_ref[0],video_lock};
            ddr_ready_ref<={ddr_ready_ref[0],ddr_init_done && ddr_pll_lock};
            system_failed_ref<={system_failed_ref[0],system_failed};
            processed_bit_ref<={processed_bit_ref[0],processed_frames[4]};
        end
    end
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
                if(|tx_init_error)begin board_failed<=1;board_fault<=8'ha7;end
                else if(pipeline_release)begin
                    if(!ddr_ready_ref[1])begin board_failed<=1;board_fault<=8'ha3;end
                    else if(!video_lock_ref[1])begin board_failed<=1;board_fault<=8'ha4;end
                    else if(!tx_init_done)begin board_failed<=1;board_fault<=8'ha5;end
                    else if(system_failed_ref[1])begin board_failed<=1;board_fault<=8'ha6;end
                end else if(video_lock_ref[1] && ddr_ready_ref[1] && tx_init_done)
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
    wire pattern_vs,pattern_de;wire [23:0] pattern_rgb;wire [31:0] pattern_frames;
    // 27MHz source and 74.25MHz output deliberately run at different rates.
    // Native source ~=10.91 frames/s; output refresh=30Hz. Repeats are counted
    // by the production system and must not be reported as new processed fps.
    // Continue frame boundaries after a fault: the capture CDC terminates its
    // last transaction on the NEXT VS edge. Only new admissions are stopped.
    processed_output_pattern #(.WIDTH(WIDTH),.HEIGHT(HEIGHT),.HT(HT),.VT(VT),.VS(VS),.X0(X0),.Y0(Y0)) pattern(
        .clk(clk_27m),.rst_n(pipeline_reset_n),.enable(1'b1),
        .vsync_active(pattern_vs),.de(pattern_de),.rgb(pattern_rgb),.frame_counter(pattern_frames));

    `include "board/board1080-synthetic.vh"
    // Scaled synthetic stress geometry, NOT a camera calibration. Native1920
    // values exactly equal the existing bound board1080 development model.
    localparam signed [23:0] MODEL_CX=(WIDTH-1)*128,MODEL_CY=(HEIGHT-1)*128;
    localparam signed [23:0] MODEL_FX=WIDTH*128,MODEL_FY=HEIGHT*1152/5;
    localparam signed [31:0] MODEL_INV_FX=(64'd274877906944+(WIDTH*128)/2)/(WIDTH*128);
    localparam signed [31:0] MODEL_INV_FY=(64'd274877906944+(HEIGHT*1152/5)/2)/(HEIGHT*1152/5);
    wire [23:0] pixel_rgb;
    hdmi1080_video_system #(.WIDTH(WIDTH),.HEIGHT(HEIGHT),.BANK_STRIDE(1048576),
        .MAX_RADIUS_Q22(B1080_RADIUS_Q22),.HT(HT),.VT(VT),.HS(HS),.VS(VS),.X0(X0),.Y0(Y0)) system(
        .core_clk(core_clk),.pix_in_clk(clk_27m),.pix_out_clk(pix_clk),.rst_n(pipeline_reset_n),
        .capture_admit(core_reset[1] && !board_failed_core[1]),
        .scan_enable(core_reset[1] && !board_failed_core[1]),
        .external_fault(board_failed_core[1]),.external_fault_code(board_fault),
        .pix_in_vsync_active(pattern_vs),.pix_in_de(pattern_de),.pix_in_rgb(pattern_rgb),
        .cfg_out_cx(MODEL_CX),.cfg_out_cy(MODEL_CY),.cfg_src_cx(MODEL_CX),.cfg_src_cy(MODEL_CY),
        .cfg_src_fx(MODEL_FX),.cfg_src_fy(MODEL_FY),.cfg_inv_fx(MODEL_INV_FX),.cfg_inv_fy(MODEL_INV_FY),
        .cfg_k1(B1080_K1),.cfg_k2(B1080_K2),.cfg_k3(B1080_K3),.cfg_p1(B1080_P1),.cfg_p2(B1080_P2),
        .awaddr(awaddr),.araddr(araddr),.awlen(awlen),.arlen(arlen),.awvalid(awvalid),.arvalid(arvalid),
        .awready(awready),.arready(arready),.wdata(wdata),.wstrb(wstrb),.wready(wready),.wlast(wlast),
        .rdata(rdata),.rvalid(rvalid),.rlast(rlast),.rid(rid),
        .pix_hs(hs_out),.pix_vs(vs_out),.pix_de(de_out),.pix_rgb(pixel_rgb),
        .failed(system_failed),.fault(system_fault),.captured_frames(captured_frames),
        .processed_frames(processed_frames),.presented_frames(presented_frames),.underflows(underflows));
    assign {r_out,g_out,b_out}=pixel_rgb;
    assign led={board_failed || system_failed_ref[1],processed_bit_ref[1],pipeline_release,pattern_frames[4],
        tx_init_done,video_lock_ref[1],ddr_ready_ref[1],heartbeat};
endmodule
