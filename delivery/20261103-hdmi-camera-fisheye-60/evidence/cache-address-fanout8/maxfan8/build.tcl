set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676
add_design {D:/f60-work/cache-addr-probe/maxfan8/top.v}
add_design {D:/f60-work/cache-addr-probe/maxfan8/cache.v}
add_constraint {D:/f60-work/cache-addr-probe/maxfan8/clock.fdc}
compile -top_module cache_address_probe
synthesize -ads -selected_syn_tool_opt 2
dev_map
exit
