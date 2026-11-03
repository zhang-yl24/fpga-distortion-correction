set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676
add_design {D:/f60-work/system-final-h-rowpad640-fanout16/compiled/rtl/mul32_pipe.v}
add_design {D:/f60-work/system-final-h-rowpad640-fanout16/compiled/rtl/bilinear_rgb.v}
add_design {D:/f60-work/system-final-h-rowpad640-fanout16/compiled/rtl/video_async_fifo.v}
add_design {D:/f60-work/system-final-h-rowpad640-fanout16/compiled/rtl/ddr_read_arbiter.v}
add_design {D:/f60-work/system-final-h-rowpad640-fanout16/compiled/rtl/ddr_write_arbiter.v}
add_design {D:/f60-work/system-final-h-rowpad640-fanout16/compiled/rtl/ddr_video_reader.v}
add_design {D:/f60-work/system-final-h-rowpad640-fanout16/compiled/rtl/experimental/ddr_adaptive_result_writer.v}
add_design {D:/f60-work/system-final-h-rowpad640-fanout16/compiled/rtl/experimental/ddr_neighbour_cache_scatter4_rowpipe.v}
add_design {D:/f60-work/system-final-h-rowpad640-fanout16/compiled/rtl/experimental/ddr_remap_sample_scatter4_rowpipe.v}
add_design {D:/f60-work/system-final-h-rowpad640-fanout16/compiled/rtl/experimental/hdmi_camera_fisheye_core.v}
add_design {D:/f60-work/system-final-h-rowpad640-fanout16/compiled/rtl/experimental/hdmi_camera_fisheye_engine.v}
add_design {D:/f60-work/system-final-h-rowpad640-fanout16/compiled/rtl/experimental/hdmi_camera_fisheye_bank.v}
add_design {D:/f60-work/system-final-h-rowpad640-fanout16/compiled/rtl/experimental/hdmi1080_capture_cdc.v}
add_design {D:/f60-work/system-final-h-rowpad640-fanout16/compiled/rtl/experimental/hdmi1080_input_dma.v}
add_design {D:/f60-work/system-final-h-rowpad640-fanout16/compiled/rtl/experimental/hdmi_camera_fisheye_input_link.v}
add_design {D:/f60-work/system-final-h-rowpad640-fanout16/compiled/rtl/experimental/ddr_video_output_1080_board.v}
add_design {D:/f60-work/system-final-h-rowpad640-fanout16/compiled/rtl/experimental/hdmi_camera_fisheye_system_c.v}
add_design {D:/f60-work/system-final-h-rowpad640-fanout16/compiled/platform/video_base/ipcore/ddr3_test/ddr3_test.idf}
add_design {D:/f60-work/system-final-h-rowpad640-fanout16/compiled/board/bringup_pll.v}
add_design {D:/f60-work/system-final-h-rowpad640-fanout16/compiled/platform/video_base/ipcore/cfg_pll/cfg_pll.v}
add_design {D:/f60-work/system-final-h-rowpad640-fanout16/compiled/rtl/experimental/iic_dri_checked.v}
add_design {D:/f60-work/system-final-h-rowpad640-fanout16/compiled/rtl/experimental/ms7200_1080p30_rearm_ctl.v}
add_design {D:/f60-work/system-final-h-rowpad640-fanout16/compiled/rtl/experimental/ms7210_checked_ctl.v}
add_design {D:/f60-work/system-final-h-rowpad640-fanout16/compiled/rtl/experimental/ms72xx_rearm_observed_ctl.v}
add_design {D:/f60-work/system-final-h-rowpad640-fanout16/compiled/board/hdmi_camera_fisheye_top.v}
add_design {D:/f60-work/system-final-h-rowpad640-fanout16/compiled/rtl/experimental/hdmi_camera_pixel_sampler.v}
add_design {D:/f60-work/system-final-h-rowpad640-fanout16/compiled/rtl/experimental/hdmi_camera_fisheye_mapper.v}
add_design {D:/f60-work/system-final-h-rowpad640-fanout16/compiled/rtl/experimental/hdmi_camera_fisheye_rom.v}
add_design {D:/f60-work/system-final-h-rowpad640-fanout16/compiled/rtl/experimental/hdmi_camera_rgb565_quantizer.v}
add_design {D:/f60-work/system-final-h-rowpad640-fanout16/compiled/rtl/experimental/camera720_view_control.v}
add_design {D:/f60-work/system-final-h-rowpad640-fanout16/compiled/rtl/experimental/hdmi_camera_fisheye_status_uart.v}
add_design {D:/f60-work/system-final-h-rowpad640-fanout16/compiled/rtl/uart_tx.v}
add_constraint {D:/f60-work/system-final-h-rowpad640-fanout16/compiled/board/hdmi-camera-fisheye-c-internal.fdc}
add_constraint {D:/f60-work/system-final-h-rowpad640-fanout16/compiled/board/board1080-ddr-ioclk-priority.rcf}
add_design {D:/f60-work/system-final-h-rowpad640-fanout16/compiled/rtl/experimental/ddr_read_return_register.v}
add_design {D:/f60-work/system-final-h-rowpad640-fanout16/compiled/rtl/experimental/hdmi_camera_fisheye_lane.v}
add_constraint {D:/f60-work/system-final-h-rowpad640-fanout16/compiled/board/ddr-ip-clock-relations.fdc}
add_constraint {D:/f60-work/system-final-h-rowpad640-fanout16/compiled/board/gray-pointer-cdc.fdc}
add_constraint {D:/f60-work/system-final-h-rowpad640-fanout16/compiled/board/ddr-ca-maxfan16.fdc}
compile -top_module hdmi_camera_fisheye_top
synthesize -ads -selected_syn_tool_opt 2
dev_map
pnr -optimize_multi_corner_timing -fix_hold_violation -fix_hold_violation_iterations 50 -fix_hold_violation_threshold 100 -fix_hold_violation_in_route TRUE
report_timing -force_to_run -delay_type min_max -max_path 1000 -nworst 4 -report_exception TRUE -report_max_skew
