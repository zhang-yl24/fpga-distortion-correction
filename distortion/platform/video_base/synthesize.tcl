add_design {D:/English/FPGA/distortion/platform/video_base/source/rtl/fram_buf.v}
add_design {D:/English/FPGA/distortion/platform/video_base/source/rtl/rd_buf.v}
add_design {D:/English/FPGA/distortion/platform/video_base/source/rtl/rd_ctrl.v}
add_design {D:/English/FPGA/distortion/platform/video_base/source/rtl/sync_vg.v}
add_design {D:/English/FPGA/distortion/platform/video_base/source/rtl/wr_buf.v}
add_design {D:/English/FPGA/distortion/platform/video_base/source/rtl/wr_cmd_trans.v}
add_design {D:/English/FPGA/distortion/platform/video_base/source/rtl/wr_ctrl.v}
add_design {D:/English/FPGA/distortion/platform/video_base/source/rtl/wr_rd_ctrl_top.v}
add_design {D:/English/FPGA/distortion/platform/video_base/source/hdmi/iic_dri.v}
add_design {D:/English/FPGA/distortion/platform/video_base/source/hdmi/ms72xx_ctl.v}
add_design {D:/English/FPGA/distortion/platform/video_base/source/hdmi/ms7200_ctl.v}
add_design {D:/English/FPGA/distortion/platform/video_base/source/hdmi/ms7210_ctl.v}
add_design {D:/English/FPGA/distortion/platform/video_base/source/rtl/HDMI_IN_DDR3_HDMI_OUT_top.v}
add_design {D:/English/FPGA/distortion/platform/video_base/source/rtl/wr_fram_buf/wr_fram_buf.idf}
add_design {D:/English/FPGA/distortion/platform/video_base/source/rtl/rd_fram_buf/rd_fram_buf.idf}
add_design {D:/English/FPGA/distortion/platform/video_base/ipcore/pll/pll.idf}
add_design {D:/English/FPGA/distortion/platform/video_base/ipcore/ddr3_test/ddr3_test.idf}
add_design {D:/English/FPGA/distortion/platform/video_base/ipcore/cfg_pll/cfg_pll.idf}
add_constraint {D:/English/FPGA/distortion/platform/video_base/HDMI_IN_DDR3_HDMI_OUT_top.fdc}
set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676
compile -top_module HDMI_IN_DDR3_HDMI_OUT_top
synthesize -ads -selected_syn_tool_opt 2
dev_map
