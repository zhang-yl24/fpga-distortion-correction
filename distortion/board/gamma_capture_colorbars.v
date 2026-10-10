// OV5640 DVP/VGA/RGB565 setup + critical register readback + HDMI pattern.
module gamma_capture_colorbars(input clk_27m,cam_pclk,cam_vsync,cam_href,input [7:0] cam_data, output [7:0] led, output uart_txd,
    inout cam_rst_n,cam_scl,cam_sda, inout hd_scl,hd_sda,
    output rstn_out,pix_clk,hs_out,vs_out,de_out,
    output [7:0] r_out,g_out,b_out, input clk_p,clk_n,

    output                               mem_rst_n                 ,
    output                               mem_ck                    ,
    output                               mem_ck_n                  ,
    output                               mem_cke                   ,
    output                               mem_cs_n                  ,
    output                               mem_ras_n                 ,
    output                               mem_cas_n                 ,
    output                               mem_we_n                  ,
    output                               mem_odt                   ,
    output      [15-1:0] mem_a                     ,
    output      [3-1:0]    mem_ba                    ,
    inout       [4-1:0]     mem_dqs                   ,
    inout       [4-1:0]     mem_dqs_n                 ,
    inout       [32-1:0]       mem_dq                    ,
    output      [4-1:0]     mem_dm                    );
    reg [19:0] power_count=0;
    wire rst_n=&power_count;
    always @(posedge clk_27m) if(!rst_n) power_count<=power_count+1;
    reg [23:0] heart_count;
    reg heart;
    always @(posedge clk_27m) begin
        if(!rst_n) begin heart_count<=0; heart<=0; end
        else if(heart_count==13499999) begin heart_count<=0; heart<=!heart; end
        else heart_count<=heart_count+1;
    end

    wire clk_125Mhz, core_clk, ddr_init_done,ddr_pll_lock;
    wire phy_pll_lock,gpll_lock,rst_gpll_lock,ddrphy_cpd_lock;
    GTP_INBUFGDS #(.IOSTANDARD("DEFAULT"),.TERM_DIFF("ON")) u_gtp(
        .O(clk_125Mhz),.I(clk_p),.IB(clk_n));
    wire [27:0] axi_awaddr,axi_araddr;
    wire [3:0] axi_awlen,axi_arlen,axi_rid;
    wire [3:0] axi_awuser_id=0,axi_aruser_id=0;
    wire axi_awready,axi_awvalid,axi_wready,axi_wusero_last;
    wire axi_arready,axi_arvalid,axi_rlast,axi_rvalid;
    wire [255:0] axi_wdata,axi_rdata;
    wire [31:0] axi_wstrb;
    (* async_reg="true" *) reg [1:0] ddr_reset_sync=0;
    always @(posedge core_clk or negedge rst_n)
        if(!rst_n) ddr_reset_sync<=0;
        else ddr_reset_sync<={ddr_reset_sync[0],1'b1};
    reg [1:0] test_reset_sync=0;
    always @(posedge core_clk)
        if(!ddr_reset_sync[1] || !ddr_init_done) test_reset_sync<=0;
        else test_reset_sync<={test_reset_sync[0],1'b1};
    wire [3:0] test_state;
    wire test_done,test_failed;
    wire [7:0] test_fault,test_passes;
    wire [31:0] test_written,test_read,test_errors;
    wire [27:0] test_first_bad;
    (* async_reg="true" *) reg [1:0] camera_ready_ddr=0;
    always @(posedge core_clk)
        if(!ddr_reset_sync[1]) camera_ready_ddr<=0;
        else camera_ready_ddr<={camera_ready_ddr[0],camera_ready};
    wire store_arm;
    capture_warmup #(.DELAY_MS(8000)) sensor_warmup(.clk(core_clk),.rst_n(ddr_reset_sync[1]),
        .ready(test_reset_sync[1] && camera_ready_ddr[1]),.armed(store_arm));
    `include "D:/English/FPGA/distortion/board/calibration-trial.vh"
    `include "D:/English/FPGA/distortion/board/rotation-domain.vh"
    wire verify_failed;wire [7:0] verify_fault;wire [31:0] pairs_completed;
    wire serial_valid,serial_ready,serial_done,serial_busy;wire [7:0] serial_data;
    gamma_frozen_capture #(.MAX_RADIUS_Q22(ROT_MAX_R2_Q22)) pipeline(.cam_clk(cam_pclk),.core_clk(core_clk),.rst_n(ddr_reset_sync[1]),.ready(store_arm),
        .vsync(!cam_vsync),.href(!cam_href),.data(cam_data),
        .cfg_out_cx(CAL_OUT_CX),.cfg_out_cy(CAL_OUT_CY),.cfg_src_cx(CAL_SRC_CX),.cfg_src_cy(CAL_SRC_CY),
        .cfg_src_fx(CAL_SRC_FX),.cfg_src_fy(CAL_SRC_FY),.cfg_inv_fx(CAL_INV_FX),.cfg_inv_fy(CAL_INV_FY),
        .cfg_k1(CAL_K1),.cfg_k2(CAL_K2),.cfg_k3(CAL_K3),.cfg_p1(CAL_P1),.cfg_p2(CAL_P2),
        .awaddr(axi_awaddr),.awlen(axi_awlen),.awvalid(axi_awvalid),.awready(axi_awready),
        .wdata(axi_wdata),.wstrb(axi_wstrb),.wready(axi_wready),.wlast(axi_wusero_last),
        .araddr(axi_araddr),.arlen(axi_arlen),.arvalid(axi_arvalid),.arready(axi_arready),
        .rdata(axi_rdata),.rvalid(axi_rvalid),.rlast(axi_rlast),.rid(axi_rid),
        .byte_valid(serial_valid),.byte_ready(serial_ready),.byte_done(serial_done),.byte_data(serial_data),
        .failed(verify_failed),.fault(verify_fault),.pairs_completed(pairs_completed));
    uart_tx #(.CLOCK_HZ(125000000),.BAUD(921600)) serial(.clk(core_clk),.rst_n(ddr_reset_sync[1]),
        .start(serial_valid && serial_ready),.data(serial_data),.tx(uart_txd),.busy(serial_busy),.done(serial_done));
    assign serial_ready=!serial_busy;
        ddr3_test u_ddr3_test_h (
             .ref_clk                   (clk_125Mhz            ),
             .resetn                    (rstn_out           ),// input
             .ddr_init_done             (ddr_init_done      ),// output

             .pll_lock                  (ddr_pll_lock           ),// output

             .core_clk                  (core_clk),                                  // output

             .phy_pll_lock              (phy_pll_lock),                          // output
             .gpll_lock                 (gpll_lock),                                // output
             .rst_gpll_lock             (rst_gpll_lock),                        // output
             .ddrphy_cpd_lock           (ddrphy_cpd_lock),                    // output
             //.ddr_init_done             (ddr_init_done),                        // output


             .axi_awaddr                (axi_awaddr         ),// input [27:0]
             .axi_awuser_ap             (1'b0               ),// input
             .axi_awuser_id             (axi_awuser_id      ),// input [3:0]
             .axi_awlen                 (axi_awlen          ),// input [3:0]
             .axi_awready               (axi_awready        ),// output
             .axi_awvalid               (axi_awvalid        ),// input
             .axi_wdata                 (axi_wdata          ),
             .axi_wstrb                 (axi_wstrb          ),// input [31:0]
             .axi_wready                (axi_wready         ),// output
             .axi_wusero_id             (                   ),// output [3:0]
             .axi_wusero_last           (axi_wusero_last    ),// output
             .axi_araddr                (axi_araddr         ),// input [27:0]
             .axi_aruser_ap             (1'b0               ),// input
             .axi_aruser_id             (axi_aruser_id      ),// input [3:0]
             .axi_arlen                 (axi_arlen          ),// input [3:0]
             .axi_arready               (axi_arready        ),// output
             .axi_arvalid               (axi_arvalid        ),// input
             .axi_rdata                 (axi_rdata          ),// output [255:0]
             .axi_rid                   (axi_rid            ),// output [3:0]
             .axi_rlast                 (axi_rlast          ),// output
             .axi_rvalid                (axi_rvalid         ),// output

             .apb_clk                   (1'b0               ),// input
             .apb_rst_n                 (1'b1               ),// input
             .apb_sel                   (1'b0               ),// input
             .apb_enable                (1'b0               ),// input
             .apb_addr                  (8'b0               ),// input [7:0]
             .apb_write                 (1'b0               ),// input
             .apb_ready                 (                   ), // output
             .apb_wdata                 (16'b0              ),// input [15:0]
             .apb_rdata                 (                   ),// output [15:0]
//             .apb_int                   (                   ),// output

             .mem_rst_n                 (mem_rst_n          ),// output
             .mem_ck                    (mem_ck             ),// output
             .mem_ck_n                  (mem_ck_n           ),// output
             .mem_cke                   (mem_cke            ),// output
             .mem_cs_n                  (mem_cs_n           ),// output
             .mem_ras_n                 (mem_ras_n          ),// output
             .mem_cas_n                 (mem_cas_n          ),// output
             .mem_we_n                  (mem_we_n           ),// output
             .mem_odt                   (mem_odt            ),// output
             .mem_a                     (mem_a              ),// output [14:0]
             .mem_ba                    (mem_ba             ),// output [2:0]
             .mem_dqs                   (mem_dqs            ),// inout [3:0]
             .mem_dqs_n                 (mem_dqs_n          ),// inout [3:0]
             .mem_dq                    (mem_dq             ),// inout [31:0]
             .mem_dm                    (mem_dm             ),// output [3:0]
             //debug

  .dbg_gate_start(1'b0),                      // input
  .dbg_cpd_start(1'b0),                        // input
  .dbg_ddrphy_rst_n(1'b1),                  // input
  .dbg_gpll_scan_rst(1'b0),                // input
  .samp_position_dyn_adj(1'b0),        // input
  .init_samp_position_even(32'd0),    // input [31:0]
  .init_samp_position_odd(32'd0),      // input [31:0]
  .wrcal_position_dyn_adj(1'b0),      // input
  .init_wrcal_position(32'd0),            // input [31:0]
  .force_read_clk_ctrl(1'b0),            // input
  .init_slip_step(16'd0),                      // input [15:0]
  .init_read_clk_ctrl(12'd0),              // input [11:0]
  .debug_calib_ctrl(),                  // output [33:0]
  .dbg_slice_status(),                  // output [67:0]
  .dbg_slice_state(),                    // output [87:0]
  .debug_data(),                              // output [275:0]
  .dbg_dll_upd_state(),                // output [1:0]
  .debug_gpll_dps_phase(),          // output [8:0]
  .dbg_rst_dps_state(),                // output [2:0]
  .dbg_tran_err_rst_cnt(),          // output [5:0]
  .dbg_ddrphy_init_fail(),          // output
  .debug_cpd_offset_adj(1'b0),          // input
  .debug_cpd_offset_dir(1'b0),          // input
  .debug_cpd_offset(10'd0),                  // input [9:0]
  .debug_dps_cnt_dir0(),              // output [9:0]
  .debug_dps_cnt_dir1(),              // output [9:0]
  .ck_dly_en(1'b0),                                // input
  .init_ck_dly_step(8'h0),                  // input [7:0]
  .ck_dly_set_bin(),                      // output [7:0]
  .align_error(),                            // output
  .debug_rst_state(),                    // output [3:0]
  .debug_cpd_state()                     // output [3:0]
       );


    wire [15:0] sensor_id; wire [7:0] cam_errors;
    wire cam_complete,cam_match,hd_ready,pll_lock;
    wire [3:0] hd_error;
    wire camera_ready,camera_failed;
    wire [15:0] camera_failed_address;
    wire [8:0] camera_writes;
    wire [8:0] camera_noacks;
    wire [7:0] camera_observed,camera_expected;
    ov5640_colorbars_init #(.DYNAMIC_PAD_MASK(1)) camera(.trial_pad_mask(16'h7ff0),.clk(clk_27m),.rst_n(rst_n),.cam_rst_n(cam_rst_n),
        .cam_scl(cam_scl),.cam_sda(cam_sda),.sensor_id(sensor_id),
        .ready(camera_ready),.failed(camera_failed),.error_code(cam_errors),
        .failed_address(camera_failed_address),.commands_written(camera_writes),.verified_write_noacks(camera_noacks),
        .observed_value(camera_observed),.expected_value(camera_expected));
    assign cam_complete=camera_ready || camera_failed;
    assign cam_match=camera_ready;
    assign rstn_out=rst_n;
    hdmi_tx_init hdmi(.clk(clk_27m),.rst_n(rst_n),.hd_scl(hd_scl),.hd_sda(hd_sda),
        .ready(hd_ready),.error(hd_error));
    bringup_pll video_pll(.clkin1(clk_27m),.clkout0(pix_clk),.lock(pll_lock));
    (* async_reg="true" *) reg [1:0] pixel_reset_sync=0;
    always @(posedge pix_clk or negedge pll_lock)
        if(!pll_lock) pixel_reset_sync<=0;
        else pixel_reset_sync<={pixel_reset_sync[0],1'b1};
    wire preview_ready;
    camera_preview picture(.cam_clk(cam_pclk),.rst_n(rst_n && pll_lock),.cam_ready(camera_ready),
        .vsync(!cam_vsync),.href(!cam_href),.data(cam_data),.pix_clk(pix_clk),
        .hs(hs_out),.vs(vs_out),.de(de_out),.r(r_out),.g(g_out),.b(b_out),.display_valid(preview_ready));
    assign led={verify_failed,preview_ready,|hd_error,|cam_errors,pll_lock,hd_ready,cam_match,heart};
endmodule
