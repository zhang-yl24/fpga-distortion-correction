set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676
add_design {D:/f60-work/cdc/fifo-probe-native/fifo_cdc_probe.v}
add_design {D:/f60/delivery/20261103-hdmi-camera-fisheye-60/rtl/video_async_fifo.v}
add_constraint {D:/f60-work/cdc/gray-constraint-probe/gray.fdc}
compile -top_module fifo_cdc_probe
synthesize -ads -selected_syn_tool_opt 2
dev_map
pnr
report_timing -force_to_run -delay_type min_max -max_path 1000 -nworst 4 -report_exception TRUE -report_max_skew
exit
