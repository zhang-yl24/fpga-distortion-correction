add_design {D:/English/FPGA/distortion/rtl/experimental/capture_warmup.v}
add_design {D:/English/FPGA/distortion/rtl/camera_preview.v}
add_design {D:/English/FPGA/distortion/rtl/ddr_uart_frame.v}
add_design {D:/English/FPGA/distortion/rtl/rgb565_burst_pack.v}
add_design {D:/English/FPGA/distortion/rtl/video_async_fifo.v}
add_design {D:/English/FPGA/distortion/rtl/camera_live_bridge.v}
add_design {D:/English/FPGA/distortion/rtl/ddr_video_writer.v}
add_design {D:/English/FPGA/distortion/rtl/dvp_rgb565_capture.v}
add_design {D:/English/FPGA/distortion/rtl/dvp_monitor.v}
add_design {D:/English/FPGA/distortion/rtl/reg16_i2c.v}
add_design {D:/English/FPGA/distortion/rtl/uart_tx.v}
add_design {D:/English/FPGA/distortion/rtl/video_pattern.v}
add_design {D:/English/FPGA/distortion/rtl/mul32_pipe.v}
add_design {D:/English/FPGA/distortion/rtl/ddr_remap_sample.v}
add_design {D:/English/FPGA/distortion/rtl/bilinear_rgb.v}
add_design {D:/English/FPGA/distortion/rtl/pixel_inverse_rotation.v}
add_design {D:/English/FPGA/distortion/rtl/bounded_brown_inverse_mapper.v}
add_design {D:/English/FPGA/distortion/rtl/experimental/gamma_frozen_capture.v}
add_design {D:/English/FPGA/distortion/rtl/experimental/adaptive_gamma_frame_engine.v}
add_design {D:/English/FPGA/distortion/rtl/experimental/rotated_remap_core_gamma.v}
add_design {D:/English/FPGA/distortion/rtl/experimental/ddr_adaptive_result_writer.v}
add_design {D:/English/FPGA/distortion/rtl/experimental/ddr_adaptive_cache.v}
add_design {D:/English/FPGA/distortion/rtl/experimental/adaptive_gamma_stream.v}
add_design {D:/English/FPGA/distortion/rtl/experimental/adaptive_gamma_tagged.v}
add_design {D:/English/FPGA/distortion/rtl/experimental/ov5640_colorbars_init.v}
add_design {D:/English/FPGA/distortion/platform/video_base/ipcore/ddr3_test/ddr3_test.idf}
add_design {D:/English/FPGA/distortion/board/hdmi_tx_init.v}
add_design {D:/English/FPGA/distortion/board/gamma_capture_colorbars.v}
add_design {D:/English/FPGA/distortion/board/bringup_pll.v}
add_constraint {D:/English/FPGA/distortion/board/gamma_capture_colorbars.fdc}
set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676
compile -top_module gamma_capture_colorbars
synthesize -ads -selected_syn_tool_opt 2
dev_map
pnr -optimize_multi_corner_timing -fix_hold_violation -fix_hold_violation_iterations 50 -fix_hold_violation_threshold 100 -fix_hold_violation_in_route TRUE
report_timing -max_path 5
gen_bit_stream -scbv {High Voltage} -unused_io_status UNUSED
