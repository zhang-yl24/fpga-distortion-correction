add_design {D:/English/FPGA/distortion/rtl/rgb565_burst_pack.v}
add_design {D:/English/FPGA/distortion/rtl/video_async_fifo.v}
add_design {D:/English/FPGA/distortion/rtl/camera_live_bridge.v}
add_design {D:/English/FPGA/distortion/rtl/ddr_video_writer.v}
add_design {D:/English/FPGA/distortion/rtl/ddr_video_reader.v}
add_design {D:/English/FPGA/distortion/rtl/ddr_video_output.v}
add_design {D:/English/FPGA/distortion/rtl/ddr_corrected_video.v}
add_design {D:/English/FPGA/distortion/rtl/remap_frame_engine.v}
add_design {D:/English/FPGA/distortion/rtl/ddr_read_arbiter.v}
add_design {D:/English/FPGA/distortion/rtl/ddr_write_arbiter.v}
add_design {D:/English/FPGA/distortion/rtl/ddr_result_writer.v}
add_design {D:/English/FPGA/distortion/rtl/brown_remap_core.v}
add_design {D:/English/FPGA/distortion/rtl/brown_inverse_mapper.v}
add_design {D:/English/FPGA/distortion/rtl/mul32_pipe.v}
add_design {D:/English/FPGA/distortion/rtl/ddr_remap_sample.v}
add_design {D:/English/FPGA/distortion/rtl/ddr_neighbour_cache.v}
add_design {D:/English/FPGA/distortion/rtl/bilinear_rgb.v}
add_design {D:/English/FPGA/distortion/platform/video_base/ipcore/ddr3_test/ddr3_test.idf}
add_design {D:/English/FPGA/distortion/rtl/dvp_rgb565_capture.v}
add_design {D:/English/FPGA/distortion/rtl/dvp_monitor.v}
add_design {D:/English/FPGA/distortion/rtl/reg16_i2c.v}
add_design {D:/English/FPGA/distortion/rtl/uart_tx.v}
add_design {D:/English/FPGA/distortion/rtl/ov5640_init.v}
add_design {D:/English/FPGA/distortion/board/hdmi_tx_init.v}
add_design {D:/English/FPGA/distortion/rtl/video_pattern.v}
add_design {D:/English/FPGA/distortion/board/corrected_video.v}
add_design {D:/English/FPGA/distortion/board/bringup_pll.v}
add_constraint {D:/English/FPGA/distortion/board/corrected_video.fdc}
set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676
# DB reuse requires explicit project setup; pds_shell otherwise starts with PGL12G.
pnr -force_to_run -input_db_file {D:/English/FPGA/distortion/build/corrected_video/device_map/corrected_video_map.adf} -input_place_db_file {D:/English/FPGA/distortion/build/corrected_video/place_route/corrected_video_plc.adf} -optimize_multi_corner_timing -fix_hold_violation -fix_hold_violation_iterations 50 -fix_hold_violation_threshold 100 -fix_hold_violation_in_route TRUE
report_timing -max_path 5
set timing_file [open {D:/English/FPGA/distortion/build/corrected_video/place_route/corrected_video_timing_summary_after_hold_fix.txt} r]
set timing_summary [read $timing_file]
close $timing_file
if {[string first {All Constraints Met} $timing_summary] < 0} {error {Timing failed; refusing bitstream generation}}
gen_bit_stream -force_to_run -scbv {High Voltage} -unused_io_status UNUSED
