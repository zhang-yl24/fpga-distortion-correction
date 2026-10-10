// Continuous native 640x480 camera2 -> two DDR banks -> 720p HDMI, with CRC32 at source, DDR read and output.
module live_video(input clk_27m,cam_pclk,cam_vsync,cam_href,input [7:0] cam_data, output [7:0] led, output uart_txd,
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
    ddr_live_video pipeline(.cam_clk(cam_pclk),.core_clk(core_clk),.pix_clk(pix_clk),
        .rst_n(rst_n && pll_lock),.ready(store_arm),.vsync(!cam_vsync),.href(!cam_href),.data(cam_data),
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
            pixel_ack_sync<=0;pixel_snapshot_request<=0;
        end else begin
            request_sync<={request_sync[0],snapshot_request};
            pixel_ack_sync<={pixel_ack_sync[0],pixel_snapshot_ack};
            if(request_sync[1]!=snapshot_ack) pixel_snapshot_request<=request_sync[1];
            if(request_sync[1]!=snapshot_ack && pixel_ack_sync[1]==request_sync[1]) begin
                held_status<={4'h9,pixel_held[128],snapshot_failed,snapshot_fault,live_captured,live_read,live_ownership,28'b0,8'b0};
                held_checksums<={live_source_crc,live_read_crc};held_pixel_status<=pixel_held;
                snapshot_ack<=request_sync[1];
            end
        end
    end
    always @(posedge clk_27m) begin
        if(!rst_n) begin ack_sync<=0;ack_seen<=0;ddr_status<=0;ddr_checksums<=0;pixel_status<=0;init_sync<=0;ddr_pll_sync<=0;end
        else begin
            ack_sync<={ack_sync[0],snapshot_ack};
            init_sync<={init_sync[0],ddr_init_done};ddr_pll_sync<={ddr_pll_sync[0],ddr_pll_lock};
            if(ack_sync[1]!=ack_seen) begin
                ddr_status<=held_status;ddr_checksums<=held_checksums;pixel_status<=held_pixel_status;ack_seen<=ack_sync[1];
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
                30:message="C";
                31:message="=";
                32:message=hexchar(report_edges[23:20]);
                33:message=hexchar(report_edges[19:16]);
                34:message=hexchar(report_edges[15:12]);
                35:message=hexchar(report_edges[11:8]);
                36:message=hexchar(report_edges[7:4]);
                37:message=hexchar(report_edges[3:0]);
                38:message=" ";
                39:message="F";
                40:message="=";
                41:message=hexchar(report_frames[31:28]);
                42:message=hexchar(report_frames[27:24]);
                43:message=hexchar(report_frames[23:20]);
                44:message=hexchar(report_frames[19:16]);
                45:message=hexchar(report_frames[15:12]);
                46:message=hexchar(report_frames[11:8]);
                47:message=hexchar(report_frames[7:4]);
                48:message=hexchar(report_frames[3:0]);
                49:message=" ";
                50:message="P";
                51:message="=";
                52:message=hexchar(report_pixels[31:28]);
                53:message=hexchar(report_pixels[27:24]);
                54:message=hexchar(report_pixels[23:20]);
                55:message=hexchar(report_pixels[19:16]);
                56:message=hexchar(report_pixels[15:12]);
                57:message=hexchar(report_pixels[11:8]);
                58:message=hexchar(report_pixels[7:4]);
                59:message=hexchar(report_pixels[3:0]);
                60:message=" ";
                61:message="L";
                62:message="=";
                63:message=hexchar(report_lines[15:12]);
                64:message=hexchar(report_lines[11:8]);
                65:message=hexchar(report_lines[7:4]);
                66:message=hexchar(report_lines[3:0]);
                67:message=" ";
                68:message="W";
                69:message="F";
                70:message="=";
                71:message=hexchar(report_ddr_status[131:128]);
                72:message=hexchar(report_ddr_status[127:124]);
                73:message=hexchar(report_ddr_status[123:120]);
                74:message=hexchar(report_ddr_status[119:116]);
                75:message=hexchar(report_ddr_status[115:112]);
                76:message=hexchar(report_ddr_status[111:108]);
                77:message=hexchar(report_ddr_status[107:104]);
                78:message=hexchar(report_ddr_status[103:100]);
                79:message=" ";
                80:message="R";
                81:message="F";
                82:message="=";
                83:message=hexchar(report_ddr_status[99:96]);
                84:message=hexchar(report_ddr_status[95:92]);
                85:message=hexchar(report_ddr_status[91:88]);
                86:message=hexchar(report_ddr_status[87:84]);
                87:message=hexchar(report_ddr_status[83:80]);
                88:message=hexchar(report_ddr_status[79:76]);
                89:message=hexchar(report_ddr_status[75:72]);
                90:message=hexchar(report_ddr_status[71:68]);
                91:message=" ";
                92:message="P";
                93:message="F";
                94:message="=";
                95:message=hexchar(report_pixel_status[127:124]);
                96:message=hexchar(report_pixel_status[123:120]);
                97:message=hexchar(report_pixel_status[119:116]);
                98:message=hexchar(report_pixel_status[115:112]);
                99:message=hexchar(report_pixel_status[111:108]);
                100:message=hexchar(report_pixel_status[107:104]);
                101:message=hexchar(report_pixel_status[103:100]);
                102:message=hexchar(report_pixel_status[99:96]);
                103:message=" ";
                104:message="U";
                105:message="F";
                106:message="=";
                107:message=hexchar(report_pixel_status[95:92]);
                108:message=hexchar(report_pixel_status[91:88]);
                109:message=hexchar(report_pixel_status[87:84]);
                110:message=hexchar(report_pixel_status[83:80]);
                111:message=hexchar(report_pixel_status[79:76]);
                112:message=hexchar(report_pixel_status[75:72]);
                113:message=hexchar(report_pixel_status[71:68]);
                114:message=hexchar(report_pixel_status[67:64]);
                115:message=" ";
                116:message="M";
                117:message="F";
                118:message="=";
                119:message=hexchar(report_pixel_status[63:60]);
                120:message=hexchar(report_pixel_status[59:56]);
                121:message=hexchar(report_pixel_status[55:52]);
                122:message=hexchar(report_pixel_status[51:48]);
                123:message=hexchar(report_pixel_status[47:44]);
                124:message=hexchar(report_pixel_status[43:40]);
                125:message=hexchar(report_pixel_status[39:36]);
                126:message=hexchar(report_pixel_status[35:32]);
                127:message=" ";
                128:message="O";
                129:message="W";
                130:message="=";
                131:message=hexchar(report_ddr_status[67:64]);
                132:message=hexchar(report_ddr_status[63:60]);
                133:message=hexchar(report_ddr_status[59:56]);
                134:message=hexchar(report_ddr_status[55:52]);
                135:message=hexchar(report_ddr_status[51:48]);
                136:message=hexchar(report_ddr_status[47:44]);
                137:message=hexchar(report_ddr_status[43:40]);
                138:message=hexchar(report_ddr_status[39:36]);
                139:message=" ";
                140:message="X";
                141:message="=";
                142:message=hexchar(report_ddr_status[139:136]);
                143:message=hexchar(report_ddr_status[135:132]);
                144:message=" ";
                145:message="C";
                146:message="S";
                147:message="=";
                148:message=hexchar(report_checksums[63:60]);
                149:message=hexchar(report_checksums[59:56]);
                150:message=hexchar(report_checksums[55:52]);
                151:message=hexchar(report_checksums[51:48]);
                152:message=hexchar(report_checksums[47:44]);
                153:message=hexchar(report_checksums[43:40]);
                154:message=hexchar(report_checksums[39:36]);
                155:message=hexchar(report_checksums[35:32]);
                156:message=" ";
                157:message="R";
                158:message="S";
                159:message="=";
                160:message=hexchar(report_checksums[31:28]);
                161:message=hexchar(report_checksums[27:24]);
                162:message=hexchar(report_checksums[23:20]);
                163:message=hexchar(report_checksums[19:16]);
                164:message=hexchar(report_checksums[15:12]);
                165:message=hexchar(report_checksums[11:8]);
                166:message=hexchar(report_checksums[7:4]);
                167:message=hexchar(report_checksums[3:0]);
                168:message=" ";
                169:message="P";
                170:message="S";
                171:message="=";
                172:message=hexchar(report_pixel_status[31:28]);
                173:message=hexchar(report_pixel_status[27:24]);
                174:message=hexchar(report_pixel_status[23:20]);
                175:message=hexchar(report_pixel_status[19:16]);
                176:message=hexchar(report_pixel_status[15:12]);
                177:message=hexchar(report_pixel_status[11:8]);
                178:message=hexchar(report_pixel_status[7:4]);
                179:message=hexchar(report_pixel_status[3:0]);
                180:message=13;181:message=10;
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
            snapshot_request<=0;report_checksums<=0;report_pixel_status<=0;report_ddr_status<=0;report_ddr_init<=0;report_ddr_pll<=0;
            report_sum<=0;report_edges<=0;report_frames<=0;report_pixels<=0;report_lines<=0;report_odd<=0;
            report_state<=0; report_index<=0; report_timer<=0; tx_start<=0; tx_data<=0;
            report_observed<=0;report_expected<=0;report_noacks<=0;report_camera_ready<=0;report_writes<=0;report_failed_address<=0;
            report_id<=0; report_errors<=0; report_hd_error<=0; report_hd_ready<=0;
        end else begin
            tx_start<=0;
            case(report_state)
                0: if(report_timer==27000000-1 && cam_complete) begin
                    snapshot_request<=!snapshot_request;report_checksums<=ddr_checksums;report_pixel_status<=pixel_status;report_ddr_status<=ddr_status;report_ddr_init<=init_sync[1];report_ddr_pll<=ddr_pll_sync[1];
                    report_sum<=dvp_sum;report_edges<=dvp_edges;report_frames<=dvp_frames;report_pixels<=dvp_pixels;report_lines<=dvp_lines;report_odd<=dvp_odd;
                    report_observed<=camera_observed;report_expected<=camera_expected;report_noacks<=camera_noacks;report_camera_ready<=camera_ready;report_writes<=camera_writes;report_failed_address<=camera_failed_address;
                    report_id<=sensor_id; report_errors<=cam_errors;
                    report_hd_error<=hd_error; report_hd_ready<=hd_ready;
                    report_timer<=0; report_index<=0; report_state<=1;
                end else if(report_timer<27000000-1) report_timer<=report_timer+1;
                1: begin tx_data<=message(report_index); tx_start<=1; report_state<=2; end
                2: if(tx_done) begin
                    if(report_index==181) report_state<=0;
                    else begin report_index<=report_index+1; report_state<=1; end
                end
                default: report_state<=0;
            endcase
        end
    end
endmodule
