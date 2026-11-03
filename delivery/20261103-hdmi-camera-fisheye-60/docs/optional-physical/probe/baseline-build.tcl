set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676
add_design {D:/f60-work/ddr-contract/pds/fanout-probe/fanout_probe.v}
compile -top_module fanout_probe
synthesize -ads -selected_syn_tool_opt 2
exit
