add_design D:/English/FPGA/distortion/board/heartbeat.v
add_constraint D:/English/FPGA/distortion/board/heartbeat.fdc
set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676
compile -top_module heartbeat
synthesize -ads -selected_syn_tool_opt 2
dev_map
pnr
gen_bit_stream -scbv {High Voltage} -unused_io_status UNUSED
