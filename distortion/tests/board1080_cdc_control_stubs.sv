`timescale 1ns/1ps
// TEST-ONLY opaque stubs. NEVER add this file to a physical board build.
// Only board1080_top control wiring is real in this test. No physical IP,
// geometry/status algorithm, System datapath, FIFO or DDR function is modeled.
// TEST-ONLY independent core125MHz/config10MHz/video~74.25MHz oscillators; not PLL models.
// DDR core clock is held low while its common reset input is low.
// Port declarations below are auto-extracted from the actual source headers.

// HEADER_BINDING {"Module":"cfg_pll","Path":"platform/video_base/ipcore/cfg_pll/cfg_pll.v","HeaderSHA256":"fe156fa552eb4545bcd5847469a4e635ecafd9ad7233c9107fcfdeda280ef858"}
module cfg_pll (
    
    output wire clkout0,
    
    input wire clkin1,
    
    output wire lock           
    );
    reg test_lock=0;
    reg test_clk=0;always #50 test_clk=~test_clk;
    assign clkout0=test_clk;
    assign lock=test_lock;
endmodule

// HEADER_BINDING {"Module":"bringup_pll","Path":"board/bringup_pll.v","HeaderSHA256":"5a9a80eeff31f8e199e0e142d2cdd97b362756a3142f22961423846aaf1f5012"}
module bringup_pll (
    
    output wire clkout0,
    
    input wire clkin1,
    
    output wire lock           
    );
    reg test_lock=0;
    reg test_clk=0;initial begin #1.733;forever #6.734 test_clk=~test_clk;end
    assign clkout0=test_clk;
    assign lock=test_lock;
endmodule

// HEADER_BINDING {"Module":"ddr3_test","Path":"platform/video_base/ipcore/ddr3_test/ddr3_test.v","HeaderSHA256":"0bc0f913caf04efb66cd7cc4cbdfa8c84ca4483660699e1663ccc47e78e3bf7e"}
module ddr3_test #(
 
   parameter MEM_ROW_WIDTH       = 15          ,
    
   parameter MEM_COLUMN_WIDTH    = 10          ,
   
   parameter MEM_BANK_WIDTH      = 3           ,
  
  parameter MEM_DQ_WIDTH         =  32         ,
  
  parameter MEM_DM_WIDTH         =  4         ,
  
  parameter MEM_DQS_WIDTH        =  4         ,
   
   parameter CTRL_ADDR_WIDTH     = MEM_ROW_WIDTH + MEM_COLUMN_WIDTH + MEM_BANK_WIDTH        
  )(                                                              
   input                              ref_clk                       ,    
   input                              resetn                        ,            
   output                             core_clk                      ,            
   output                             pll_lock                      ,    
   output                             phy_pll_lock                  ,
   output                             gpll_lock                     ,        
   output                             rst_gpll_lock                 ,            
   output                             ddrphy_cpd_lock               ,      
   output                             ddr_init_done                 ,            

   input  [CTRL_ADDR_WIDTH-1:0]       axi_awaddr                    ,
   input                              axi_awuser_ap                 ,
   input  [3:0]                       axi_awuser_id                 ,
   input  [3:0]                       axi_awlen                     ,
   output                             axi_awready                   ,
   input                              axi_awvalid                   ,

   input  [8*MEM_DQ_WIDTH-1:0]        axi_wdata                     ,
   input  [MEM_DQ_WIDTH-1:0]          axi_wstrb                     ,
   output                             axi_wready                    ,
   output [3:0]                       axi_wusero_id                 ,
   output                             axi_wusero_last               ,

   input  [CTRL_ADDR_WIDTH-1:0]       axi_araddr                    ,
   input                              axi_aruser_ap                 ,
   input  [3:0]                       axi_aruser_id                 ,
   input  [3:0]                       axi_arlen                     ,
   output                             axi_arready                   ,
   input                              axi_arvalid                   ,

   output [8*MEM_DQ_WIDTH-1:0]        axi_rdata                     ,
   output [3:0]                       axi_rid                       ,
   output                             axi_rlast                     ,
   output                             axi_rvalid                    ,

   input                              apb_clk                       ,
   input                              apb_rst_n                     ,
   input                              apb_sel                       ,
   input                              apb_enable                    ,
   input  [7:0]                       apb_addr                      ,
   input                              apb_write                     ,
   output                             apb_ready                     ,
   input  [15:0]                      apb_wdata                     ,
   output [15:0]                      apb_rdata                     ,


   output                             mem_cs_n                      ,

   output                             mem_rst_n                     ,                       
   output                             mem_ck                        ,
   output                             mem_ck_n                      ,
   output                             mem_cke                       ,
   output                             mem_ras_n                     ,
   output                             mem_cas_n                     ,
   output                             mem_we_n                      , 
   output                             mem_odt                       ,
   output [MEM_ROW_WIDTH-1:0]         mem_a                         ,   
   output [MEM_BANK_WIDTH-1:0]        mem_ba                        ,   
   inout  [MEM_DQS_WIDTH-1:0]         mem_dqs                       ,
   inout  [MEM_DQS_WIDTH-1:0]         mem_dqs_n                     ,
   inout  [MEM_DQ_WIDTH-1:0]          mem_dq                        ,
   output [MEM_DM_WIDTH-1:0]          mem_dm                        , 

   //debug
   input                              dbg_gate_start                ,
   input                              dbg_cpd_start                 ,
   input                              dbg_ddrphy_rst_n              ,
   input                              dbg_gpll_scan_rst             ,

   input                              samp_position_dyn_adj         ,
   input  [8*MEM_DQS_WIDTH-1:0]       init_samp_position_even       ,
   input  [8*MEM_DQS_WIDTH-1:0]       init_samp_position_odd        ,

   input                              wrcal_position_dyn_adj        ,
   input  [8*MEM_DQS_WIDTH-1:0]       init_wrcal_position           ,
 
   input                              force_read_clk_ctrl           ,
   input  [4*MEM_DQS_WIDTH-1:0]       init_slip_step                ,  
   input  [3*MEM_DQS_WIDTH-1:0]       init_read_clk_ctrl            ,

   output [33:0]                      debug_calib_ctrl              ,
   output [17*MEM_DQS_WIDTH -1:0]     dbg_slice_status              ,
   output [22*MEM_DQS_WIDTH -1:0]     dbg_slice_state               ,
   output [69*MEM_DQS_WIDTH -1:0]     debug_data                    ,
   output [1:0]                       dbg_dll_upd_state             ,
   output [8:0]                       debug_gpll_dps_phase          ,
   
   output [2:0]                       dbg_rst_dps_state             ,
   output [5:0]                       dbg_tran_err_rst_cnt          ,
   output                             dbg_ddrphy_init_fail          , 
   
   input                              debug_cpd_offset_adj          ,
   input                              debug_cpd_offset_dir          ,
   input  [9:0]                       debug_cpd_offset              ,  
   output [9:0]                       debug_dps_cnt_dir0            , 
   output [9:0]                       debug_dps_cnt_dir1            ,

   input                              ck_dly_en                     ,
   input  [7:0]                       init_ck_dly_step              ,
   output [7:0]                       ck_dly_set_bin                ,
  
   output                             align_error                   ,
   output [3:0]                       debug_rst_state               ,
   output [3:0]                       debug_cpd_state               
);
    reg test_pll_lock=0,test_init_done=0;
    reg test_clk=0;initial begin #0.571;forever #4 test_clk=~test_clk;end
    assign core_clk=resetn ? test_clk:1'b0;
    assign pll_lock=test_pll_lock;
    assign phy_pll_lock=test_pll_lock;
    assign gpll_lock=test_pll_lock;
    assign rst_gpll_lock=test_pll_lock;
    assign ddrphy_cpd_lock=test_pll_lock;
    assign ddr_init_done=test_init_done;
    assign axi_awready='0;
    assign axi_wready='0;
    assign axi_wusero_id='0;
    assign axi_wusero_last='0;
    assign axi_arready='0;
    assign axi_rdata='0;
    assign axi_rid='0;
    assign axi_rlast='0;
    assign axi_rvalid='0;
    assign apb_ready='0;
    assign apb_rdata='0;
    assign mem_cs_n='0;
    assign mem_rst_n=resetn;
    assign mem_ck='0;
    assign mem_ck_n='0;
    assign mem_cke='0;
    assign mem_ras_n='0;
    assign mem_cas_n='0;
    assign mem_we_n='0;
    assign mem_odt='0;
    assign mem_a='0;
    assign mem_ba='0;
    assign mem_dm='0;
    assign debug_calib_ctrl='0;
    assign dbg_slice_status='0;
    assign dbg_slice_state='0;
    assign debug_data='0;
    assign dbg_dll_upd_state='0;
    assign debug_gpll_dps_phase='0;
    assign dbg_rst_dps_state='0;
    assign dbg_tran_err_rst_cnt='0;
    assign dbg_ddrphy_init_fail='0;
    assign debug_dps_cnt_dir0='0;
    assign debug_dps_cnt_dir1='0;
    assign ck_dly_set_bin='0;
    assign align_error='0;
    assign debug_rst_state='0;
    assign debug_cpd_state='0;
    assign mem_dqs='z;
    assign mem_dqs_n='z;
    assign mem_dq='z;
endmodule

// HEADER_BINDING {"Module":"ms72xx_ctl","Path":"platform/video_base/source/hdmi/ms72xx_ctl.v","HeaderSHA256":"13e4968ac59ac390a02cebdf51e06c6bb8184243992cf74ae72220a605a9f7eb"}
module ms72xx_ctl(
    input       clk,
    input       rst_n,
    
    output      init_over_rx,
    output      init_over,
    output      iic_scl,
    inout       iic_sda
);
    reg test_rx_done=0,test_tx_done=0;
    assign init_over_rx=rst_n && test_rx_done;
    assign init_over=rst_n && test_tx_done;
    assign iic_scl=1'b1;
    assign iic_sda='z;
endmodule

// HEADER_BINDING {"Module":"hdmi1080_input_status","Path":"rtl/experimental/hdmi1080_input_status.v","HeaderSHA256":"366b2e825e9a35c9f85e84cef37d5639ef0a8c06efe9b59c1aa6f9b1f595eeea"}
module hdmi1080_input_status #(
    parameter WIDTH=1920,HEIGHT=1080,HTOTAL=2200,VTOTAL=1125,
    parameter ACTIVITY_REF_CYCLES=27000,PCLK_WINDOW_MIN=73500,PCLK_WINDOW_MAX=75000
)(
    input ref_clk,pix_clk,rst_n,pix_vs,pix_hs,pix_de,
    output normalized_vs,output qualified,failed,output [7:0] fault,
    output polarity_known_ref,vs_inactive_ref,hs_inactive_ref,
    output [31:0] good_frames,bad_frames,pclk_edges_per_window,
    output [15:0] last_pixels_per_line,last_lines
);
    reg test_qualified=0,test_failed=0;reg [7:0] test_fault=0;
    assign normalized_vs=pix_vs;
    assign qualified=rst_n && test_qualified && !test_failed;
    assign failed=rst_n && test_failed;
    assign fault=failed ? test_fault:8'h00;
    assign polarity_known_ref=qualified;
    assign vs_inactive_ref='0;
    assign hs_inactive_ref='0;
    assign good_frames=qualified ? 32'd2:32'd0;
    assign bad_frames='0;
    assign pclk_edges_per_window=qualified ? 32'd74250:32'd0;
    assign last_pixels_per_line='0;
    assign last_lines='0;
endmodule

// HEADER_BINDING {"Module":"hdmi1080_video_system","Path":"rtl/experimental/hdmi1080_video_system.v","HeaderSHA256":"eff487f0880c79d182fc1e4aaee4a4e447ba22b34a486ef964d69c936295cfe9"}
module hdmi1080_video_system #(
    parameter WIDTH=1920,HEIGHT=1080,BANK_STRIDE=1048576,MAX_RADIUS_Q22=8388608,
    HT=2200,VT=1125,HS=44,VS=5,X0=192,Y0=41
)(
    input core_clk,pix_in_clk,pix_out_clk,rst_n,
    input capture_admit,scan_enable,external_fault,input [7:0] external_fault_code,
    input pix_in_vsync_active,pix_in_de,input [23:0] pix_in_rgb,
    input signed [23:0] cfg_out_cx,cfg_out_cy,cfg_src_cx,cfg_src_cy,cfg_src_fx,cfg_src_fy,
    input signed [31:0] cfg_inv_fx,cfg_inv_fy,cfg_k1,cfg_k2,cfg_k3,cfg_p1,cfg_p2,
    output [27:0] awaddr,araddr,output [3:0] awlen,arlen,
    output awvalid,arvalid,input awready,arready,
    output [255:0] wdata,output [31:0] wstrb,input wready,wlast,
    input [255:0] rdata,input rvalid,rlast,input [3:0] rid,
    output pix_hs,pix_vs,pix_de,output [23:0] pix_rgb,output display_valid,
    output failed,output [7:0] fault,
    output [31:0] captured_frames,processed_frames,
    output wire [31:0] presented_frames,scan_good_frames,scan_repeat_frames,scan_blank_frames,
    output [31:0] underflows,mismatches,
    output wire source_commit,output wire [31:0] source_commit_id,output wire source_commit_bank,
    output wire [31:0] source_crc,source_pixels,
    output source_release,output [31:0] source_release_id,output released_bank,
    output result_publish,output [31:0] publish_id,output [1:0] publish_bank,
    output [31:0] last_process_cycles,
    output [31:0] pix_frame_id,output pix_frame_bank,pix_frame_start,pix_frame_last,pix_pixel_valid,
    output pix_done_toggle,pix_done_good,output [31:0] pix_done_crc,
    output processing,pending,display_active,write_bank,front_bank,
    output [1:0] capture_reserved,output [9:0] fifo_used,fifo_available,
    output wire [31:0] peak_fifo_used,
    output [31:0] cache_hits,cache_misses,queries,output read_busy,write_busy
);
    reg test_failed=0,test_aw_hold=0;reg [7:0] test_fault=0;
    assign awaddr=28'd2097152;
    assign araddr='0;
    assign awlen=4'd15;
    assign arlen='0;
    assign awvalid=rst_n && test_aw_hold;
    assign arvalid='0;
    assign wdata=256'h123456789abcdef00123456789abcdef0123456789abcdef0123456789abcdef0;
    assign wstrb=32'hffffffff;
    assign pix_hs='0;
    assign pix_vs='0;
    assign pix_de='0;
    assign pix_rgb='0;
    assign display_valid='0;
    assign failed=rst_n && test_failed;
    assign fault=failed ? test_fault:8'h00;
    assign captured_frames='0;
    assign processed_frames='0;
    assign presented_frames='0;
    assign scan_good_frames='0;
    assign scan_repeat_frames='0;
    assign scan_blank_frames='0;
    assign underflows='0;
    assign mismatches='0;
    assign source_commit='0;
    assign source_commit_id='0;
    assign source_commit_bank='0;
    assign source_crc='0;
    assign source_pixels='0;
    assign source_release='0;
    assign source_release_id='0;
    assign released_bank='0;
    assign result_publish='0;
    assign publish_id='0;
    assign publish_bank='0;
    assign last_process_cycles='0;
    assign pix_frame_id='0;
    assign pix_frame_bank='0;
    assign pix_frame_start='0;
    assign pix_frame_last='0;
    assign pix_pixel_valid='0;
    assign pix_done_toggle='0;
    assign pix_done_good='0;
    assign pix_done_crc='0;
    assign processing='0;
    assign pending='0;
    assign display_active='0;
    assign write_bank='0;
    assign front_bank='0;
    assign capture_reserved='0;
    assign fifo_used='0;
    assign fifo_available='0;
    assign peak_fifo_used='0;
    assign cache_hits='0;
    assign cache_misses='0;
    assign queries='0;
    assign read_busy='0;
    assign write_busy='0;
endmodule

// Vendor differential buffer signature is taken from the actual top instance.
module GTP_INBUFGDS #(parameter IOSTANDARD="DEFAULT",TERM_DIFF="ON")(
    output O,input I,IB);
    assign O=I; // TEST-ONLY: no differential/electrical behavior.
endmodule
