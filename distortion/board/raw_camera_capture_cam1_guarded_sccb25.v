// Separate bounded PGGUARD02 CAM1 candidate. Boot disarmed; UART RX B24.
// Existing CAM1 reference pinmap only; physical eye and stereo sync unverified.
// Native raw PGFRAME1 only. No lens calibration, Brown, rotation or Gamma datapath.
// Slot tag encoding: 00=unassigned, 01=CAM1, 10=CAM2, 11=reserved.
// CAM1 denotes connector slot; physical left/right and synchronization are unverified.
// OV5640 DVP/VGA/RGB565 setup + critical register readback + HDMI pattern.
module raw_camera_capture_cam1_guarded_sccb25(input clk_27m,cam_pclk,cam_vsync,cam_href,input [7:0] cam_data, output [7:0] led, output uart_txd,input uart_rxd,
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
    // Connector slot only; no physical left/right or stereo-sync claim.
    localparam [31:0] GUARDED_BUILD_TAG=32'h52473125,CAMERA_ID=32'h43414d31;
    localparam [1:0] CAMERA_SLOT=2'b01;
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
    // Independent ADC at 27MHz; source bus held until core acknowledges.
    wire temp_valid,temp_failed,temp_over;wire [7:0] temp_fault;wire [4:0] temp_alarm;
    wire [15:0] temp_raw;wire [11:0] temp_code;wire [31:0] temp_age,temp_samples,temp_conversions;
    logos2_temperature_monitor temperature(.clk(clk_27m),.rst_n(rst_n),
        .sample_valid(temp_valid),.sample_pulse(),.failed(temp_failed),.fault(temp_fault),
        .raw_word(temp_raw),.code12(temp_code),.sample_age(temp_age),.samples(temp_samples),
        .conversions(temp_conversions),.over_temp(temp_over),.alarm(temp_alarm));
    wire safety_ok,safety_valid;wire [31:0] safety_age;
    wire held_temp_valid,held_temp_failed,held_temp_over;wire [7:0] held_temp_fault;
    wire [4:0] held_temp_alarm;wire [15:0] held_temp_raw;wire [11:0] held_temp_code;
    wire [31:0] held_temp_age,held_temp_samples,held_temp_conversions;wire [95:0] held_camera_info;
    wire [95:0] source_camera_info={14'b0,camera_ready,camera_failed,hd_ready,hd_error,pll_lock,
        camera_expected,camera_observed,camera_noacks,camera_writes,camera_failed_address,cam_errors,sensor_id};
    guarded_temperature_cdc temperature_cdc(.source_clk(clk_27m),.core_clk(core_clk),.arst_n(rst_n),
        .sample_valid(temp_valid),.failed(temp_failed),.fault(temp_fault),.raw_word(temp_raw),.code12(temp_code),
        .sample_age(temp_age),.samples(temp_samples),.conversions(temp_conversions),.over_temp(temp_over),
        .alarm(temp_alarm),.source_extra(source_camera_info),.healthy(safety_ok),.snapshot_valid(safety_valid),
        .snapshot_event(),.snapshot_age(safety_age),.held_valid(held_temp_valid),.held_failed(held_temp_failed),
        .held_fault(held_temp_fault),.held_raw(held_temp_raw),.held_code(held_temp_code),.held_age(held_temp_age),
        .held_samples(held_temp_samples),.held_conversions(held_temp_conversions),.held_over_temp(held_temp_over),
        .held_alarm(held_temp_alarm),.held_extra(held_camera_info));
    wire raw_failed,raw_done,raw_locked,armed,in_flight,requires_reset;
    wire [7:0] raw_fault;wire [3:0] raw_state,stop_reason;
    wire serial_valid,serial_ready,serial_done,serial_busy;wire [7:0] serial_data;
    wire rx_valid,rx_framing_error;wire [7:0] rx_data;
    uart_rx_control #(.CLOCK_HZ(125000000),.BAUD(921600)) rx_control(.clk(core_clk),.rst_n(ddr_reset_sync[1]),
        .rx(uart_rxd),.valid(rx_valid),.data(rx_data),.framing_error(rx_framing_error));
    guarded_capture_controller #(.BUILD_TAG(GUARDED_BUILD_TAG),.CAMERA_ID(CAMERA_ID),.CAMERA_SLOT(CAMERA_SLOT))
        controller(.core_clk(core_clk),.cam_clk(cam_pclk),.rst_n(ddr_reset_sync[1]),
        .camera_ready(camera_ready_ddr[1]),.ddr_ready(test_reset_sync[1]),.warmup_ready(store_arm),
        .safety_ok(safety_ok),.safety_snapshot_valid(safety_valid),.safety_snapshot_age(safety_age),
        .temp_valid(held_temp_valid),.temp_failed(held_temp_failed),.temp_fault(held_temp_fault),
        .temp_over(held_temp_over),.temp_alarm(held_temp_alarm),.temp_raw(held_temp_raw),.temp_code(held_temp_code),
        .temp_age(held_temp_age),.temp_samples(held_temp_samples),.temp_conversions(held_temp_conversions),.camera_info(held_camera_info),
        .rx_valid(rx_valid),.rx_data(rx_data),.rx_framing_error(rx_framing_error),
        .vsync(!cam_vsync),.href(!cam_href),.data(cam_data),
        .awaddr(axi_awaddr),.awlen(axi_awlen),.awvalid(axi_awvalid),.awready(axi_awready),
        .wdata(axi_wdata),.wstrb(axi_wstrb),.wready(axi_wready),.wlast(axi_wusero_last),
        .araddr(axi_araddr),.arlen(axi_arlen),.arvalid(axi_arvalid),.arready(axi_arready),
        .rdata(axi_rdata),.rvalid(axi_rvalid),.rlast(axi_rlast),.rid(axi_rid),
        .byte_valid(serial_valid),.byte_ready(serial_ready),.byte_done(serial_done),.byte_data(serial_data),
        .bank_locked(raw_locked),.raw_done(raw_done),.raw_failed(raw_failed),.raw_fault(raw_fault),.raw_state(raw_state),
        .armed(armed),.in_flight(in_flight),.requires_reset(requires_reset),.stop_reason(stop_reason),
        .admitted_frames(),.completed_frames(),.remaining_frames(),.remaining_cycles(),.capture_active(),
        .core_idle(),.ready_for_grant(),.status_active(),.status_pending(),.raw_uart_locked(),
        .command_busy(),.reply_event(),.frame_sequence(),.grant_accepted(),.grant_rejected());
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
    ov5640_cadence_trial_init #(.DYNAMIC_PAD_MASK(1),.I2C_QUARTER_CYCLES(270)) camera(.trial_pad_mask(16'h7ff0),.clk(clk_27m),.rst_n(rst_n),.cam_rst_n(cam_rst_n),
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
    assign led={raw_failed,!safety_ok,requires_reset,in_flight,armed,ddr_init_done,cam_match,heart};
endmodule
