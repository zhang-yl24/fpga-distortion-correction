add_design {D:/English/FPGA/distortion/rtl/reg16_i2c.v}
add_design {D:/English/FPGA/distortion/rtl/uart_tx.v}
add_design {D:/English/FPGA/distortion/rtl/camera_id_probe.v}
add_design {D:/English/FPGA/distortion/board/hdmi_tx_init.v}
add_design {D:/English/FPGA/distortion/rtl/video_pattern.v}
add_design {D:/English/FPGA/distortion/board/bringup.v}
add_design {D:/English/FPGA/distortion/board/bringup_pll.v}
add_constraint {D:/English/FPGA/distortion/board/bringup.fdc}
set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676
compile -top_module bringup
synthesize -ads -selected_syn_tool_opt 2
dev_map
pnr
report_timing -from [get_clocks pixel_clk] -to [get_ports {r_out[*] g_out[*] b_out[*] de_out hs_out vs_out}] -max_path 2
gen_bit_stream -scbv {High Voltage} -unused_io_status UNUSED
