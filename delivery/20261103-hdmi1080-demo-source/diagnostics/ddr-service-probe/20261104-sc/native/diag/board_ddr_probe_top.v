`timescale 1ns/1ps
// Isolated finite native DDR UI measurement. No HDMI/image pipeline/Flash.
module board1080_top(
 input clk_27m,clk_p,clk_n,reset_n,output telemetry_tx,output [7:0] led,
 output mem_rst_n,mem_ck,mem_ck_n,mem_cke,mem_cs_n,mem_ras_n,mem_cas_n,mem_we_n,mem_odt,
 output [14:0] mem_a,output [2:0] mem_ba,
 inout [3:0] mem_dqs,mem_dqs_n,inout [31:0] mem_dq,output [3:0] mem_dm
);
    (* async_reg="true", PAP_ASYNC_REG=1 *) reg [1:0] key_reset_sync=0;
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
 (* PAP_ASYNC_REG=1 *) reg [1:0] core_reset_sync=0,core_init_sync=0;
 always @(posedge core_clk or negedge global_reset_n)
  if(!global_reset_n)begin core_reset_sync<=0;core_init_sync<=0;end
  else begin core_reset_sync<={core_reset_sync[0],1'b1};core_init_sync<={core_init_sync[0],ddr_init_done && ddr_pll_lock};end
 wire probe_started,probe_done,probe_failed;wire[7:0]probe_fault;wire[3:0]probe_phase;wire[1:0]probe_active_group;
 wire[31:0]probe_writes,probe_reads,read_beats,data_error_beats,protocol_errors,timeouts,crc_error_groups;
 wire[95:0] group_count,ar_wait_min,ar_wait_max,ar_wait_sum,first_min,first_max,first_sum,last_min,last_max,last_sum,actual_crc,expected_crc;
 ddr_ui_service_probe #(.READS_PER_GROUP(16),.TIMEOUT_CYCLES(4096),.GAP_CYCLES(8)) probe(
 .clk(core_clk),.rst_n(core_reset_sync[1]),.init_done(core_init_sync[1]),
 .awaddr(awaddr),.araddr(araddr),.awlen(awlen),.arlen(arlen),.awvalid(awvalid),.arvalid(arvalid),.awready(awready),.arready(arready),
 .wdata(wdata),.wstrb(wstrb),.wready(wready),.wlast(wlast),.rdata(rdata),.rvalid(rvalid),.rlast(rlast),.rid(rid),
 .started(probe_started),.done(probe_done),.failed(probe_failed),.fault(probe_fault),.phase(probe_phase),.active_group(probe_active_group),
 .writes(probe_writes),.reads(probe_reads),.read_beats(read_beats),.data_error_beats(data_error_beats),.protocol_errors(protocol_errors),.timeouts(timeouts),.crc_error_groups(crc_error_groups),
 .group_count(group_count),.ar_wait_min(ar_wait_min),.ar_wait_max(ar_wait_max),.ar_wait_sum(ar_wait_sum),
 .first_min(first_min),.first_max(first_max),.first_sum(first_sum),.last_min(last_min),.last_max(last_max),.last_sum(last_sum),.actual_crc(actual_crc),.expected_crc(expected_crc));
 wire snapshot_captured_core,snapshot_valid_ref;
 ddr_probe_readout readout(
 .core_clk(core_clk),.ref_clk(clk_27m),.global_reset_n(global_reset_n),.key0_async(reset_n),.ddr_init_done_async(ddr_init_done),.ddr_pll_lock_async(ddr_pll_lock),
 .probe_started(probe_started),.probe_done(probe_done),.probe_failed(probe_failed),.probe_init_done(core_init_sync[1]),.probe_fault(probe_fault),.probe_phase(probe_phase),.probe_active_group(probe_active_group),
 .probe_writes(probe_writes),.probe_reads(probe_reads),.data_error_beats(data_error_beats),.protocol_errors(protocol_errors),.timeouts(timeouts),.crc_error_groups(crc_error_groups),
 .group_count(group_count),.ar_wait_min(ar_wait_min),.ar_wait_max(ar_wait_max),.ar_wait_sum(ar_wait_sum),
 .first_min(first_min),.first_max(first_max),.first_sum(first_sum),.last_min(last_min),.last_max(last_max),.last_sum(last_sum),.actual_crc(actual_crc),.expected_crc(expected_crc),
 .telemetry_tx(telemetry_tx),.snapshot_captured_core(snapshot_captured_core),.snapshot_valid_ref(snapshot_valid_ref));
 reg[24:0]heartbeat=0;
 (* PAP_ASYNC_REG=1 *) reg[6:0] status_sync1=0,status_sync2=0;
 always @(posedge clk_27m)begin heartbeat<=heartbeat+1'b1;status_sync1<={probe_failed,probe_done,probe_started,ddr_init_done,ddr_pll_lock,global_reset_n,snapshot_valid_ref};status_sync2<=status_sync1;end
 assign led={status_sync2,heartbeat[23]};
endmodule
