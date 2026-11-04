set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676
add_design {D:/f60-work/ddr-contract/pds/fanout-probe/fanout_probe.v}
add_constraint {D:/f60/delivery/20261103-hdmi-camera-fisheye-60/docs/optional-physical/ddr-ca-maxfan16.fdc}
compile -top_module fanout_probe
synthesize -ads -selected_syn_tool_opt 2
exit
