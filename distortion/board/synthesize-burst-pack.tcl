add_design D:/English/FPGA/distortion/rtl/rgb565_burst_pack.v
add_design D:/English/FPGA/distortion/board/burst_pack_synthesis_top.v
set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676
compile -top_module burst_pack_synthesis_top
synthesize -ads -selected_syn_tool_opt 2
dev_map
# Standalone device mapping only; no unconstrained bitstream is generated.
