// Native camera2 -> frozen source DDR -> arithmetic remap/bilinear -> two result banks -> HDMI.
// KEY0 rotation demo and internal ADC temperature telemetry; optical model remains bounded.
module corrected_rotate(input key0_n,clk_27m,cam_pclk,cam_vsync,cam_href,input [7:0] cam_data, output [7:0] led, output uart_txd,
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
    wire store_arm=test_reset_sync[1] && camera_ready_ddr[1];
    wire preview_ready,live_failed;
    wire [7:0] live_fault;
    wire [31:0] live_captured,live_read,live_output,live_underflow,live_mismatch,live_ownership;
    wire [31:0] live_source_crc,live_read_crc,live_pixel_crc;
    `include "D:/English/FPGA/distortion/board/calibration-trial.vh"
    wire [31:0] corrected_frames,process_cycles,cache_hits,cache_misses,completed_queries,result_crc;

    `include "D:/English/FPGA/distortion/board/rotation-domain.vh"
    wire rotation_valid,rotation_automatic;
    wire [31:0] rotation_phase,result_phase;
    wire signed [31:0] rotation_cos,rotation_sin;
    rotation_demo_control rotation_control(.clk(core_clk),.rst_n(test_reset_sync[1]),.key_n(key0_n),
        .auto_mode(rotation_automatic),.cfg_valid(rotation_valid),.cfg_phase(rotation_phase),
        .cfg_cos(rotation_cos),.cfg_sin(rotation_sin));
    wire temp_valid,temp_failed,temp_over,temp_pulse;wire [4:0] temp_alarm;
    wire [7:0] temp_fault;wire [15:0] temp_raw;wire [11:0] temp_code;
    wire [31:0] temp_age,temp_conversions,temp_samples;
    logos2_temperature_monitor temperature(.clk(clk_27m),.rst_n(rst_n),
        .sample_valid(temp_valid),.sample_pulse(temp_pulse),.failed(temp_failed),.fault(temp_fault),
        .raw_word(temp_raw),.code12(temp_code),.sample_age(temp_age),.conversions(temp_conversions),.samples(temp_samples),
        .over_temp(temp_over),.alarm(temp_alarm));
    reg [32:0] held_rotation=0,rotation_status=0,report_rotation=0;
    reg [63:0] report_temperature=0;
    ddr_rotated_video #(.MAX_RADIUS_Q22(ROT_MAX_R2_Q22)) pipeline(.cam_clk(cam_pclk),.core_clk(core_clk),.pix_clk(pix_clk),
        .rst_n(rst_n && pll_lock),.ready(store_arm),.vsync(!cam_vsync),.href(!cam_href),.data(cam_data),
        .cfg_out_cx(CAL_OUT_CX),.cfg_out_cy(CAL_OUT_CY),.cfg_src_cx(CAL_SRC_CX),.cfg_src_cy(CAL_SRC_CY),
        .cfg_src_fx(CAL_SRC_FX),.cfg_src_fy(CAL_SRC_FY),.cfg_inv_fx(CAL_INV_FX),.cfg_inv_fy(CAL_INV_FY),
        .cfg_k1(CAL_K1),.cfg_k2(CAL_K2),.cfg_k3(CAL_K3),.cfg_p1(CAL_P1),.cfg_p2(CAL_P2),
        .cfg_rotation_valid(rotation_valid),.cfg_rotation_phase(rotation_phase),.result_phase(result_phase),
        .cfg_rot_cx(24'sd81792),.cfg_rot_cy(24'sd61312),.cfg_rot_cos(rotation_cos),.cfg_rot_sin(rotation_sin),
        .processed_frames(corrected_frames),.last_process_cycles(process_cycles),
        .cache_hits(cache_hits),.cache_misses(cache_misses),.completed_queries(completed_queries),.latest_result_checksum(result_crc),
        .awaddr(axi_awaddr),.araddr(axi_araddr),.awlen(axi_awlen),.arlen(axi_arlen),
        .awvalid(axi_awvalid),.arvalid(axi_arvalid),.awready(axi_awready),.arready(axi_arready),
        .wdata(axi_wdata),.wstrb(axi_wstrb),.wready(axi_wready),.wlast(axi_wusero_last),
        .rdata(axi_rdata),.rvalid(axi_rvalid),.rlast(axi_rlast),.rid(axi_rid),
        .hs(hs_out),.vs(vs_out),.de(de_out),.r(r_out),.g(g_out),.b(b_out),
        .display_valid(preview_ready),.output_frames(live_output),.underflows(live_underflow),
        .pixel_mismatches(live_mismatch),.pixel_checksum(live_pixel_crc),
        .captured_frames(live_captured),.ownership_errors(live_ownership),.read_frames(live_read),
        .read_checksum(live_read_crc),.latest_source_checksum(live_source_crc),.failed(live_failed),.fault(live_fault));
    // CORE -> PIX -> CORE -> SYS held-bus snapshot. Multi-bit counters
    // are captured coherently, never sampled directly while they change.
    reg snapshot_request=0,snapshot_ack=0;
    (* async_reg="true" *) reg [1:0] request_sync=0,ack_sync=0;
    (* async_reg="true" *) reg [1:0] init_sync=0,ddr_pll_sync=0;
    (* async_reg="true" *) reg [1:0] pixel_snapshot_reset=0,pixel_request_sync=0,pixel_ack_sync=0;
    reg pixel_snapshot_request=0,pixel_snapshot_ack=0;
    reg [128:0] pixel_held=0,held_pixel_status=0,pixel_status=0,report_pixel_status=0;
    reg [145:0] held_status=0,ddr_status=0,report_ddr_status=0;
    reg [63:0] held_checksums=0,ddr_checksums=0,report_checksums=0;
    reg [159:0] held_engine=0,engine_status=0,report_engine=0;
    reg ack_seen=0;
    always @(posedge pix_clk or negedge rst_n)
        if(!rst_n) pixel_snapshot_reset<=0;else pixel_snapshot_reset<={pixel_snapshot_reset[0],1'b1};
    always @(posedge pix_clk) begin
        if(!pixel_snapshot_reset[1]) begin pixel_request_sync<=0;pixel_snapshot_ack<=0;pixel_held<=0;end
        else begin
            pixel_request_sync<={pixel_request_sync[0],pixel_snapshot_request};
            if(pixel_request_sync[1]!=pixel_snapshot_ack) begin
                pixel_held<={preview_ready,live_output,live_underflow,live_mismatch,live_pixel_crc};
                pixel_snapshot_ack<=pixel_request_sync[1];
            end
        end
    end
    wire snapshot_failed=live_failed || pixel_held[95:64]!=0 || pixel_held[63:32]!=0;
    wire [7:0] snapshot_fault=live_failed ? live_fault:pixel_held[95:64]!=0 ? 8'h41:pixel_held[63:32]!=0 ? 8'h42:8'h00;
    always @(posedge core_clk) begin
        if(!ddr_reset_sync[1]) begin
            request_sync<=0;snapshot_ack<=0;held_status<=0;held_checksums<=0;held_pixel_status<=0;
            pixel_ack_sync<=0;pixel_snapshot_request<=0;held_engine<=0;held_rotation<=0;
        end else begin
            request_sync<={request_sync[0],snapshot_request};
            pixel_ack_sync<={pixel_ack_sync[0],pixel_snapshot_ack};
            if(request_sync[1]!=snapshot_ack) pixel_snapshot_request<=request_sync[1];
            if(request_sync[1]!=snapshot_ack && pixel_ack_sync[1]==request_sync[1]) begin
                held_status<={4'h9,pixel_held[128],snapshot_failed,snapshot_fault,live_captured,live_read,live_ownership,28'b0,8'b0};
                held_engine<={corrected_frames,process_cycles,cache_hits,cache_misses,result_crc};held_rotation<={rotation_automatic,result_phase};
                held_checksums<={live_source_crc,live_read_crc};held_pixel_status<=pixel_held;
                snapshot_ack<=request_sync[1];
            end
        end
    end
    always @(posedge clk_27m) begin
        if(!rst_n) begin ack_sync<=0;ack_seen<=0;engine_status<=0;rotation_status<=0;ddr_status<=0;ddr_checksums<=0;pixel_status<=0;init_sync<=0;ddr_pll_sync<=0;end
        else begin
            ack_sync<={ack_sync[0],snapshot_ack};
            init_sync<={init_sync[0],ddr_init_done};ddr_pll_sync<={ddr_pll_sync[0],ddr_pll_lock};
            if(ack_sync[1]!=ack_seen) begin
                engine_status<=held_engine;rotation_status<=held_rotation;ddr_status<=held_status;ddr_checksums<=held_checksums;pixel_status<=held_pixel_status;ack_seen<=ack_sync[1];
            end
        end
    end
    reg report_ddr_init,report_ddr_pll;
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
    ov5640_init #(.DYNAMIC_PAD_MASK(1)) camera(.trial_pad_mask(16'h7ff0),.clk(clk_27m),.rst_n(rst_n),.cam_rst_n(cam_rst_n),
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
    assign led={ddr_status[140],preview_ready,|hd_error,|cam_errors,pll_lock,hd_ready,cam_match,heart};
    wire [23:0] dvp_edges;
    wire [31:0] dvp_frames,dvp_pixels,dvp_sum;
    wire [15:0] dvp_lines;
    wire dvp_odd;
    dvp_monitor monitor(.sysclk(clk_27m),.rst_n(rst_n),.pclk(cam_pclk),
        .vsync(!cam_vsync),.href(!cam_href),.data(cam_data),.edges_per_window(dvp_edges),
        .frames(dvp_frames),.last_pixels(dvp_pixels),.last_checksum(dvp_sum),.last_lines(dvp_lines),.last_odd(dvp_odd));
    reg [23:0] report_edges;
    reg [31:0] report_frames,report_pixels,report_sum;
    reg [15:0] report_lines;
    reg report_odd;
    function [7:0] hexchar;
        input [3:0] nibble;
        begin hexchar=nibble<10 ? 8'd48+nibble:8'd65+nibble-10; end
    endfunction
    reg [15:0] report_id;
    reg [7:0] report_errors;
    reg [3:0] report_hd_error;
    reg report_hd_ready;
    reg report_camera_ready;
    reg [8:0] report_writes;
    reg [8:0] report_noacks;
    reg [7:0] report_observed,report_expected;
    reg [15:0] report_failed_address;
    function [7:0] message;
        input [7:0] idx;
        begin
            case(idx)
                0:message="C";
                1:message="A";
                2:message="M";
                3:message="=";
                4:message=hexchar(report_id[15:12]);
                5:message=hexchar(report_id[11:8]);
                6:message=hexchar(report_id[7:4]);
                7:message=hexchar(report_id[3:0]);
                8:message=" ";
                9:message="E";
                10:message="=";
                11:message=hexchar(report_errors[7:4]);
                12:message=hexchar(report_errors[3:0]);
                13:message=" ";
                14:message="I";
                15:message="=";
                16:message=report_camera_ready ? "1":"0";
                17:message=" ";
                18:message="H";
                19:message="=";
                20:message=report_hd_ready ? "1":"0";
                21:message=" ";
                22:message="D";
                23:message="=";
                24:message=report_ddr_init ? "1":"0";
                25:message=" ";
                26:message="V";
                27:message="=";
                28:message=report_pixel_status[128] ? "1":"0";
                29:message=" ";
                30:message="W";
                31:message="F";
                32:message="=";
                33:message=hexchar(report_ddr_status[131:128]);
                34:message=hexchar(report_ddr_status[127:124]);
                35:message=hexchar(report_ddr_status[123:120]);
                36:message=hexchar(report_ddr_status[119:116]);
                37:message=hexchar(report_ddr_status[115:112]);
                38:message=hexchar(report_ddr_status[111:108]);
                39:message=hexchar(report_ddr_status[107:104]);
                40:message=hexchar(report_ddr_status[103:100]);
                41:message=" ";
                42:message="C";
                43:message="F";
                44:message="=";
                45:message=hexchar(report_engine[159:156]);
                46:message=hexchar(report_engine[155:152]);
                47:message=hexchar(report_engine[151:148]);
                48:message=hexchar(report_engine[147:144]);
                49:message=hexchar(report_engine[143:140]);
                50:message=hexchar(report_engine[139:136]);
                51:message=hexchar(report_engine[135:132]);
                52:message=hexchar(report_engine[131:128]);
                53:message=" ";
                54:message="P";
                55:message="F";
                56:message="=";
                57:message=hexchar(report_pixel_status[127:124]);
                58:message=hexchar(report_pixel_status[123:120]);
                59:message=hexchar(report_pixel_status[119:116]);
                60:message=hexchar(report_pixel_status[115:112]);
                61:message=hexchar(report_pixel_status[111:108]);
                62:message=hexchar(report_pixel_status[107:104]);
                63:message=hexchar(report_pixel_status[103:100]);
                64:message=hexchar(report_pixel_status[99:96]);
                65:message=" ";
                66:message="U";
                67:message="F";
                68:message="=";
                69:message=hexchar(report_pixel_status[95:92]);
                70:message=hexchar(report_pixel_status[91:88]);
                71:message=hexchar(report_pixel_status[87:84]);
                72:message=hexchar(report_pixel_status[83:80]);
                73:message=hexchar(report_pixel_status[79:76]);
                74:message=hexchar(report_pixel_status[75:72]);
                75:message=hexchar(report_pixel_status[71:68]);
                76:message=hexchar(report_pixel_status[67:64]);
                77:message=" ";
                78:message="M";
                79:message="F";
                80:message="=";
                81:message=hexchar(report_pixel_status[63:60]);
                82:message=hexchar(report_pixel_status[59:56]);
                83:message=hexchar(report_pixel_status[55:52]);
                84:message=hexchar(report_pixel_status[51:48]);
                85:message=hexchar(report_pixel_status[47:44]);
                86:message=hexchar(report_pixel_status[43:40]);
                87:message=hexchar(report_pixel_status[39:36]);
                88:message=hexchar(report_pixel_status[35:32]);
                89:message=" ";
                90:message="O";
                91:message="W";
                92:message="=";
                93:message=hexchar(report_ddr_status[67:64]);
                94:message=hexchar(report_ddr_status[63:60]);
                95:message=hexchar(report_ddr_status[59:56]);
                96:message=hexchar(report_ddr_status[55:52]);
                97:message=hexchar(report_ddr_status[51:48]);
                98:message=hexchar(report_ddr_status[47:44]);
                99:message=hexchar(report_ddr_status[43:40]);
                100:message=hexchar(report_ddr_status[39:36]);
                101:message=" ";
                102:message="X";
                103:message="=";
                104:message=hexchar(report_ddr_status[139:136]);
                105:message=hexchar(report_ddr_status[135:132]);
                106:message=" ";
                107:message="C";
                108:message="S";
                109:message="=";
                110:message=hexchar(report_checksums[63:60]);
                111:message=hexchar(report_checksums[59:56]);
                112:message=hexchar(report_checksums[55:52]);
                113:message=hexchar(report_checksums[51:48]);
                114:message=hexchar(report_checksums[47:44]);
                115:message=hexchar(report_checksums[43:40]);
                116:message=hexchar(report_checksums[39:36]);
                117:message=hexchar(report_checksums[35:32]);
                118:message=" ";
                119:message="R";
                120:message="C";
                121:message="=";
                122:message=hexchar(report_engine[31:28]);
                123:message=hexchar(report_engine[27:24]);
                124:message=hexchar(report_engine[23:20]);
                125:message=hexchar(report_engine[19:16]);
                126:message=hexchar(report_engine[15:12]);
                127:message=hexchar(report_engine[11:8]);
                128:message=hexchar(report_engine[7:4]);
                129:message=hexchar(report_engine[3:0]);
                130:message=" ";
                131:message="R";
                132:message="S";
                133:message="=";
                134:message=hexchar(report_checksums[31:28]);
                135:message=hexchar(report_checksums[27:24]);
                136:message=hexchar(report_checksums[23:20]);
                137:message=hexchar(report_checksums[19:16]);
                138:message=hexchar(report_checksums[15:12]);
                139:message=hexchar(report_checksums[11:8]);
                140:message=hexchar(report_checksums[7:4]);
                141:message=hexchar(report_checksums[3:0]);
                142:message=" ";
                143:message="P";
                144:message="S";
                145:message="=";
                146:message=hexchar(report_pixel_status[31:28]);
                147:message=hexchar(report_pixel_status[27:24]);
                148:message=hexchar(report_pixel_status[23:20]);
                149:message=hexchar(report_pixel_status[19:16]);
                150:message=hexchar(report_pixel_status[15:12]);
                151:message=hexchar(report_pixel_status[11:8]);
                152:message=hexchar(report_pixel_status[7:4]);
                153:message=hexchar(report_pixel_status[3:0]);
                154:message=" ";
                155:message="C";
                156:message="Y";
                157:message="=";
                158:message=hexchar(report_engine[127:124]);
                159:message=hexchar(report_engine[123:120]);
                160:message=hexchar(report_engine[119:116]);
                161:message=hexchar(report_engine[115:112]);
                162:message=hexchar(report_engine[111:108]);
                163:message=hexchar(report_engine[107:104]);
                164:message=hexchar(report_engine[103:100]);
                165:message=hexchar(report_engine[99:96]);
                166:message=" ";
                167:message="H";
                168:message="T";
                169:message="=";
                170:message=hexchar(report_engine[95:92]);
                171:message=hexchar(report_engine[91:88]);
                172:message=hexchar(report_engine[87:84]);
                173:message=hexchar(report_engine[83:80]);
                174:message=hexchar(report_engine[79:76]);
                175:message=hexchar(report_engine[75:72]);
                176:message=hexchar(report_engine[71:68]);
                177:message=hexchar(report_engine[67:64]);
                178:message=" ";
                179:message="M";
                180:message="S";
                181:message="=";
                182:message=hexchar(report_engine[63:60]);
                183:message=hexchar(report_engine[59:56]);
                184:message=hexchar(report_engine[55:52]);
                185:message=hexchar(report_engine[51:48]);
                186:message=hexchar(report_engine[47:44]);
                187:message=hexchar(report_engine[43:40]);
                188:message=hexchar(report_engine[39:36]);
                189:message=hexchar(report_engine[35:32]);
                190:message=" ";
                191:message="R";
                192:message="A";
                193:message="=";
                194:message=hexchar(report_rotation[31:28]);
                195:message=hexchar(report_rotation[27:24]);
                196:message=hexchar(report_rotation[23:20]);
                197:message=hexchar(report_rotation[19:16]);
                198:message=hexchar(report_rotation[15:12]);
                199:message=hexchar(report_rotation[11:8]);
                200:message=hexchar(report_rotation[7:4]);
                201:message=hexchar(report_rotation[3:0]);
                202:message=" ";
                203:message="A";
                204:message="U";
                205:message="=";
                206:message=hexchar({3'b0,report_rotation[32]});
                207:message=" ";
                208:message="T";
                209:message="V";
                210:message="=";
                211:message=hexchar({3'b0,report_temperature[63]});
                212:message=" ";
                213:message="T";
                214:message="R";
                215:message="=";
                216:message=hexchar(report_temperature[47:44]);
                217:message=hexchar(report_temperature[43:40]);
                218:message=hexchar(report_temperature[39:36]);
                219:message=hexchar(report_temperature[35:32]);
                220:message=" ";
                221:message="T";
                222:message="F";
                223:message="=";
                224:message=hexchar(report_temperature[55:52]);
                225:message=hexchar(report_temperature[51:48]);
                226:message=" ";
                227:message="T";
                228:message="A";
                229:message="=";
                230:message=hexchar(report_temperature[31:28]);
                231:message=hexchar(report_temperature[27:24]);
                232:message=hexchar(report_temperature[23:20]);
                233:message=hexchar(report_temperature[19:16]);
                234:message=hexchar(report_temperature[15:12]);
                235:message=hexchar(report_temperature[11:8]);
                236:message=hexchar(report_temperature[7:4]);
                237:message=hexchar(report_temperature[3:0]);
                238:message=" ";
                239:message="A";
                240:message="L";
                241:message="=";
                242:message=hexchar(report_temperature[63:60]);
                243:message=hexchar(report_temperature[59:56]);
                244:message=13;245:message=10;
                default:message="?";
            endcase
        end
    endfunction
    reg [1:0] report_state;
    reg [7:0] report_index;
    reg [24:0] report_timer;
    reg tx_start; reg [7:0] tx_data;
    wire tx_busy,tx_done;
    uart_tx uart(.clk(clk_27m),.rst_n(rst_n),.start(tx_start),.data(tx_data),
        .tx(uart_txd),.busy(tx_busy),.done(tx_done));
    always @(posedge clk_27m) begin
        if(!rst_n) begin
            snapshot_request<=0;report_rotation<=0;report_temperature<=0;report_checksums<=0;report_pixel_status<=0;report_engine<=0;report_ddr_status<=0;report_ddr_init<=0;report_ddr_pll<=0;
            report_sum<=0;report_edges<=0;report_frames<=0;report_pixels<=0;report_lines<=0;report_odd<=0;
            report_state<=0; report_index<=0; report_timer<=0; tx_start<=0; tx_data<=0;
            report_observed<=0;report_expected<=0;report_noacks<=0;report_camera_ready<=0;report_writes<=0;report_failed_address<=0;
            report_id<=0; report_errors<=0; report_hd_error<=0; report_hd_ready<=0;
        end else begin
            tx_start<=0;
            case(report_state)
                0: if(report_timer==27000000-1 && cam_complete) begin
                    snapshot_request<=!snapshot_request;report_rotation<=rotation_status;report_temperature<={temp_valid,temp_failed,temp_over,temp_alarm,temp_fault,temp_raw,temp_age};report_engine<=engine_status;report_checksums<=ddr_checksums;report_pixel_status<=pixel_status;report_ddr_status<=ddr_status;report_ddr_init<=init_sync[1];report_ddr_pll<=ddr_pll_sync[1];
                    report_sum<=dvp_sum;report_edges<=dvp_edges;report_frames<=dvp_frames;report_pixels<=dvp_pixels;report_lines<=dvp_lines;report_odd<=dvp_odd;
                    report_observed<=camera_observed;report_expected<=camera_expected;report_noacks<=camera_noacks;report_camera_ready<=camera_ready;report_writes<=camera_writes;report_failed_address<=camera_failed_address;
                    report_id<=sensor_id; report_errors<=cam_errors;
                    report_hd_error<=hd_error; report_hd_ready<=hd_ready;
                    report_timer<=0; report_index<=0; report_state<=1;
                end else if(report_timer<27000000-1) report_timer<=report_timer+1;
                1: begin tx_data<=message(report_index); tx_start<=1; report_state<=2; end
                2: if(tx_done) begin
                    if(report_index==245) report_state<=0;
                    else begin report_index<=report_index+1; report_state<=1; end
                end
                default: report_state<=0;
            endcase
        end
    end
endmodule
