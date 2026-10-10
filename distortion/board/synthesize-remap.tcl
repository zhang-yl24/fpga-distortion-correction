# Standalone resource/device-map check only; no board bitstream is generated.
add_design {D:/English/FPGA/distortion/rtl/bilinear_rgb.v}
add_design {D:/English/FPGA/distortion/rtl/ddr_neighbour_cache.v}
add_design {D:/English/FPGA/distortion/rtl/ddr_remap_sample.v}
add_design {D:/English/FPGA/distortion/board/remap_synthesis_top.v}
set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676
compile -top_module remap_synthesis_top
synthesize -ads -selected_syn_tool_opt 2
dev_map
