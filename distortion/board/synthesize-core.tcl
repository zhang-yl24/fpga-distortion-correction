add_design D:/English/FPGA/distortion/rtl/bilinear_rgb.v
set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676
compile -top_module bilinear_rgb
synthesize -ads -selected_syn_tool_opt 2
dev_map
# Standalone synthesis only; NO unconstrained core bitstream may be programmed.
