`timescale 1ps/1ps
// TEST ONLY: status injection; no SCCB, capture, processing or DDR implementation.

// HEADER_BINDING {"Module": "ov5640_cadence_trial_init", "Path": "rtl/experimental/ov5640_cadence_trial_init.v", "HeaderSHA256": "96d6d6dfea49af1af319a0722e41871fdd2945fe46f037717d98eca3a6d1cbcd"}
module ov5640_cadence_trial_init #(
    parameter RESET_CYCLES=270000, WAIT_CYCLES=1350000,
    MS_CYCLES=27000, I2C_QUARTER_CYCLES=68, I2C_TIMEOUT_CYCLES=1350000,
    CHECK_WRITES=1, DYNAMIC_PAD_MASK=0
)(input clk, input rst_n, inout cam_rst_n, cam_scl, cam_sda,
    input [15:0] trial_pad_mask,
    output reg [15:0] sensor_id, output reg ready, output reg failed,
    output reg [7:0] error_code, output reg [15:0] failed_address,
    output reg [8:0] commands_written, output reg [8:0] verified_write_noacks,
    output reg [7:0] observed_value, expected_value);
reg test_ready=0,test_failed=0;
reg [7:0] test_error=0;
assign cam_rst_n=rst_n ? 1'bz : 1'b0;
assign cam_scl=1'bz;
assign cam_sda=1'bz;
always @* begin
    ready=rst_n && test_ready; failed=rst_n && test_failed;
    sensor_id=rst_n ? 16'h5640 : 0; error_code=rst_n ? test_error : 0;
    failed_address=0;commands_written=0;verified_write_noacks=0;
    observed_value=0;expected_value=0;
end
endmodule

// HEADER_BINDING {"Module": "camera_vga_video_system", "Path": "rtl/experimental/camera_vga_video_system.v", "HeaderSHA256": "fd400d318d0cf440438d194673616b1bc7fa94b88f71cf51bd21769b4d612f4e"}
module camera_vga_video_system #(
    parameter WIDTH=640,HEIGHT=480,BANK_STRIDE=1048576,MAX_RADIUS_Q22=8388608,
    HT=2200,VT=1125,HS=44,VS=5,X0=192,Y0=41,
    OUTPUT_WIDTH=1920,OUTPUT_HEIGHT=1080,
    VSYNC_ACTIVE_HIGH=0,HREF_ACTIVE_HIGH=0,HIGH_BYTE_FIRST=0
)(
    input core_clk,cam_clk,pix_out_clk,rst_n,
    input capture_admit,scan_enable,external_fault,input [7:0] external_fault_code,
    input cam_vsync,cam_href,input [7:0] cam_data,
    input signed [23:0] cfg_out_cx,cfg_out_cy,cfg_src_cx,cfg_src_cy,cfg_src_fx,cfg_src_fy,
    input signed [31:0] cfg_inv_fx,cfg_inv_fy,cfg_k1,cfg_k2,cfg_k3,cfg_p1,cfg_p2,
    output [27:0] awaddr,araddr,output [3:0] awlen,arlen,
    output awvalid,arvalid,input awready,arready,
    output [255:0] wdata,output [31:0] wstrb,input wready,wlast,
    input [255:0] rdata,input rvalid,rlast,input [3:0] rid,
    output pix_hs,pix_vs,pix_de,output [23:0] pix_rgb,output display_valid,
    output failed,output [7:0] fault,
    output [31:0] captured_frames,processed_frames,
    output reg [31:0] presented_frames,scan_good_frames,scan_repeat_frames,scan_blank_frames,
    output [31:0] underflows,mismatches,
    output reg source_commit,output reg [31:0] source_commit_id,output reg source_commit_bank,
    output reg [31:0] source_crc,source_pixels,
    output source_release,output [31:0] source_release_id,output released_bank,
    output result_publish,output [31:0] publish_id,output [1:0] publish_bank,
    output [31:0] last_process_cycles,
    output [31:0] pix_frame_id,output pix_frame_bank,pix_frame_start,pix_frame_last,pix_pixel_valid,
    output pix_done_toggle,pix_done_good,output [31:0] pix_done_crc,
    output processing,pending,display_active,write_bank,front_bank,
    output [1:0] capture_reserved,output [9:0] fifo_used,fifo_available,
    output reg [31:0] peak_fifo_used,
    output [31:0] cache_hits,cache_misses,queries,output read_busy,write_busy
);
reg test_failed=0;
reg [7:0] test_fault=0;
reg [31:0] test_captured_frames=0,test_processed_frames=0;
assign failed=rst_n && test_failed;
assign fault=rst_n ? test_fault : 0;
assign captured_frames=rst_n ? test_captured_frames : 0;
assign processed_frames=rst_n ? test_processed_frames : 0;
assign awaddr=0,araddr=0,awlen=0,arlen=0,awvalid=0,arvalid=0,wdata=0,wstrb=0;
assign pix_hs=0,pix_vs=0,pix_de=0,pix_rgb=0,display_valid=0;
assign underflows=0,mismatches=0,source_release=0,source_release_id=0,released_bank=0;
assign result_publish=0,publish_id=0,publish_bank=0,last_process_cycles=0;
assign pix_frame_id=0,pix_frame_bank=0,pix_frame_start=0,pix_frame_last=0,pix_pixel_valid=0;
assign pix_done_toggle=0,pix_done_good=0,pix_done_crc=0;
assign processing=0,pending=0,display_active=0,write_bank=0,front_bank=0;
assign capture_reserved=0,fifo_used=0,fifo_available=0;
assign cache_hits=0,cache_misses=0,queries=0,read_busy=0,write_busy=0;
always @* begin
    presented_frames=rst_n ? 32'd0 : 32'd0;
    scan_good_frames=0;scan_repeat_frames=0;scan_blank_frames=0;
    source_commit=0;source_commit_id=0;source_commit_bank=0;
    source_crc=0;source_pixels=0;peak_fifo_used=0;
end
endmodule
