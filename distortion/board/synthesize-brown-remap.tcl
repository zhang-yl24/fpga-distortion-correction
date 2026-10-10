# Resource and exact-device map only. Board integration needs routed timing.
add_design {D:/English/FPGA/distortion/rtl/bilinear_rgb.v}
add_design {D:/English/FPGA/distortion/rtl/ddr_neighbour_cache.v}
add_design {D:/English/FPGA/distortion/rtl/ddr_remap_sample.v}
add_design {D:/English/FPGA/distortion/rtl/mul32_pipe.v}
add_design {D:/English/FPGA/distortion/rtl/brown_inverse_mapper.v}
add_design {D:/English/FPGA/distortion/rtl/brown_remap_core.v}
add_design {D:/English/FPGA/distortion/board/brown_remap_synthesis_top.v}
set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676
compile -top_module brown_remap_synthesis_top
synthesize -ads -selected_syn_tool_opt 2
dev_map
