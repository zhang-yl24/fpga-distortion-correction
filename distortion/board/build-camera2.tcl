add_design {D:/English/FPGA/distortion/rtl/dvp_rgb565_capture.v}
add_design {D:/English/FPGA/distortion/rtl/dvp_monitor.v}
add_design {D:/English/FPGA/distortion/rtl/reg16_i2c.v}
add_design {D:/English/FPGA/distortion/rtl/uart_tx.v}
add_design {D:/English/FPGA/distortion/rtl/ov5640_init.v}
add_design {D:/English/FPGA/distortion/board/hdmi_tx_init.v}
add_design {D:/English/FPGA/distortion/rtl/video_pattern.v}
add_design {D:/English/FPGA/distortion/board/camera2.v}
add_design {D:/English/FPGA/distortion/board/bringup_pll.v}
add_constraint {D:/English/FPGA/distortion/board/camera2.fdc}
set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676
compile -top_module camera2
synthesize -ads -selected_syn_tool_opt 2
dev_map
pnr
report_timing -max_path 5
gen_bit_stream -scbv {High Voltage} -unused_io_status UNUSED
