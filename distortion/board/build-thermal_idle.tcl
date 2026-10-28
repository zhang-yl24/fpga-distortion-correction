add_design {D:/English/FPGA/distortion/rtl/thermal_idle_telemetry.v}
add_design {D:/English/FPGA/distortion/rtl/logos2_temperature_monitor.v}
add_design {D:/English/FPGA/distortion/rtl/adc_temperature_reader.v}
add_design {D:/English/FPGA/distortion/rtl/uart_tx.v}
add_design {D:/English/FPGA/distortion/board/thermal_idle.v}
add_constraint {D:/English/FPGA/distortion/board/thermal_idle.fdc}
set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676
compile -top_module thermal_idle
synthesize -ads -selected_syn_tool_opt 2
dev_map
pnr -optimize_multi_corner_timing -fix_hold_violation -fix_hold_violation_iterations 50 -fix_hold_violation_threshold 100 -fix_hold_violation_in_route TRUE
report_timing -max_path 5
gen_bit_stream -scbv {High Voltage} -unused_io_status UNUSED
