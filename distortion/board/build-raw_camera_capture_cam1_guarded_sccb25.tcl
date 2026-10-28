add_design {D:/English/FPGA/distortion/rtl/raw_camera_capture.v}
add_design {D:/English/FPGA/distortion/rtl/experimental/capture_warmup.v}
add_design {D:/English/FPGA/distortion/rtl/camera_preview.v}
add_design {D:/English/FPGA/distortion/rtl/ddr_uart_frame.v}
add_design {D:/English/FPGA/distortion/rtl/rgb565_burst_pack.v}
add_design {D:/English/FPGA/distortion/rtl/video_async_fifo.v}
add_design {D:/English/FPGA/distortion/rtl/camera_live_bridge.v}
add_design {D:/English/FPGA/distortion/rtl/ddr_video_writer.v}
add_design {D:/English/FPGA/distortion/rtl/dvp_rgb565_capture.v}
add_design {D:/English/FPGA/distortion/rtl/reg16_i2c.v}
add_design {D:/English/FPGA/distortion/rtl/uart_tx.v}
add_design {D:/English/FPGA/distortion/rtl/video_pattern.v}
add_design {D:/English/FPGA/distortion/rtl/experimental/ov5640_cadence_trial_init.v}
add_design {D:/English/FPGA/distortion/platform/video_base/ipcore/ddr3_test/ddr3_test.idf}
add_design {D:/English/FPGA/distortion/board/hdmi_tx_init.v}
add_design {D:/English/FPGA/distortion/board/bringup_pll.v}
add_design {D:/English/FPGA/distortion/rtl/raw_capture_lease.v}
add_design {D:/English/FPGA/distortion/rtl/raw_camera_capture_guarded.v}
add_design {D:/English/FPGA/distortion/rtl/guarded_command_engine.v}
add_design {D:/English/FPGA/distortion/rtl/guarded_capture_controller.v}
add_design {D:/English/FPGA/distortion/rtl/guarded_temperature_cdc.v}
add_design {D:/English/FPGA/distortion/rtl/guarded_status_uart.v}
add_design {D:/English/FPGA/distortion/rtl/guarded_uart_arbiter.v}
add_design {D:/English/FPGA/distortion/rtl/experimental/uart_rx_control.v}
add_design {D:/English/FPGA/distortion/rtl/logos2_temperature_monitor.v}
add_design {D:/English/FPGA/distortion/rtl/adc_temperature_reader.v}
add_design {D:/English/FPGA/distortion/board/raw_camera_capture_cam1_guarded_sccb25.v}
add_constraint {D:/English/FPGA/distortion/board/raw_camera_capture_cam1_guarded_sccb25.fdc}
set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676
compile -top_module raw_camera_capture_cam1_guarded_sccb25
synthesize -ads -selected_syn_tool_opt 2
dev_map
pnr -optimize_multi_corner_timing -fix_hold_violation -fix_hold_violation_iterations 50 -fix_hold_violation_threshold 100 -fix_hold_violation_in_route TRUE
report_timing -max_path 5
gen_bit_stream -scbv {High Voltage} -unused_io_status UNUSED
