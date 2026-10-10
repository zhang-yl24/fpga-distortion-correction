add_design {D:/English/FPGA/distortion/rtl/video_async_fifo.v}
add_design {D:/English/FPGA/distortion/board/video_fifo_synthesis_top.v}
set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676
compile -top_module video_fifo_synthesis_top
synthesize -ads -selected_syn_tool_opt 2
dev_map
