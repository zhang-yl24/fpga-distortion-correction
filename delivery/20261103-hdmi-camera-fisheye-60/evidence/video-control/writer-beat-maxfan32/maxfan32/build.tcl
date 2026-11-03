set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676
set_option max_threads 2
add_design {D:/f60-work/video/writer-beat-fanout-probe-r2/maxfan32/writer.v}
add_design {D:/f60-work/video/writer-beat-fanout-probe-r2/wrapper.v}
add_constraint {D:/f60-work/video/writer-beat-fanout-probe-r2/maxfan32/clock.fdc}
compile -top_module writer_probe
synthesize -ads -selected_syn_tool_opt 2
dev_map
exit
