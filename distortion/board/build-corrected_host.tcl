add_design {D:/English/FPGA/distortion/rtl/pixel_inverse_rotation.v}
add_design {D:/English/FPGA/distortion/rtl/cordic_sincos.v}
add_design {D:/English/FPGA/distortion/rtl/experimental/uart_rx_control.v}
add_design {D:/English/FPGA/distortion/rtl/experimental/rotation_command_parser.v}
add_design {D:/English/FPGA/distortion/rtl/experimental/rotation_host_control.v}
add_design {D:/English/FPGA/distortion/rtl/adc_temperature_reader.v}
add_design {D:/English/FPGA/distortion/rtl/logos2_temperature_monitor.v}
add_design {D:/English/FPGA/distortion/rtl/experimental/rgb565_burst_pack_early.v}
add_design {D:/English/FPGA/distortion/rtl/video_async_fifo.v}
add_design {D:/English/FPGA/distortion/rtl/experimental/camera_live_bridge_early.v}
add_design {D:/English/FPGA/distortion/rtl/ddr_video_writer.v}
add_design {D:/English/FPGA/distortion/rtl/ddr_video_reader.v}
add_design {D:/English/FPGA/distortion/rtl/ddr_video_output.v}
add_design {D:/English/FPGA/distortion/rtl/experimental/ddr_adaptive_video.v}
add_design {D:/English/FPGA/distortion/rtl/experimental/adaptive_tiled_frame_engine.v}
add_design {D:/English/FPGA/distortion/rtl/ddr_read_arbiter.v}
add_design {D:/English/FPGA/distortion/rtl/ddr_write_arbiter.v}
add_design {D:/English/FPGA/distortion/rtl/experimental/ddr_adaptive_result_writer.v}
add_design {D:/English/FPGA/distortion/rtl/rotated_remap_core.v}
add_design {D:/English/FPGA/distortion/rtl/bounded_brown_inverse_mapper.v}
add_design {D:/English/FPGA/distortion/rtl/mul32_pipe.v}
add_design {D:/English/FPGA/distortion/rtl/ddr_remap_sample.v}
add_design {D:/English/FPGA/distortion/rtl/experimental/ddr_adaptive_cache.v}
add_design {D:/English/FPGA/distortion/rtl/bilinear_rgb.v}
add_design {D:/English/FPGA/distortion/platform/video_base/ipcore/ddr3_test/ddr3_test.idf}
add_design {D:/English/FPGA/distortion/rtl/dvp_rgb565_capture.v}
add_design {D:/English/FPGA/distortion/rtl/dvp_monitor.v}
add_design {D:/English/FPGA/distortion/rtl/camera_frame_period.v}
add_design {D:/English/FPGA/distortion/rtl/reg16_i2c.v}
add_design {D:/English/FPGA/distortion/rtl/uart_tx.v}
add_design {D:/English/FPGA/distortion/rtl/ov5640_init.v}
add_design {D:/English/FPGA/distortion/board/hdmi_tx_init.v}
add_design {D:/English/FPGA/distortion/rtl/video_pattern.v}
add_design {D:/English/FPGA/distortion/board/corrected_host.v}
add_design {D:/English/FPGA/distortion/board/bringup_pll.v}
add_constraint {D:/English/FPGA/distortion/board/corrected_host.fdc}
set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676
compile -force_to_run -top_module corrected_host
synthesize -force_to_run -ads -selected_syn_tool_opt 2
dev_map -force_to_run
pnr -force_to_run -gplace_seed 2 -optimize_multi_corner_timing -fix_hold_violation -fix_hold_violation_iterations 50 -fix_hold_violation_threshold 100 -fix_hold_violation_in_route TRUE
report_timing -force_to_run -max_path 5
gen_bit_stream -force_to_run -scbv {High Voltage} -unused_io_status UNUSED
