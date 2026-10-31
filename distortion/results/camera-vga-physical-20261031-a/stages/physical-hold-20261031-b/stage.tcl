set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera-vga-output/physical-hold-20261031-b/dummy.v}
if {[info script] ne {}} {
mpnr -input {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera-vga-output/physical-hold-20261031-b/input.adf}
show -design_net {_N101}
unroute -branch {_N101:M2:CLMA_351_774;}
manual_route -net {_N101} -branch {M2:CLMA_351_774} -pins {ZDNE[0]:SRB_336_726>IDNE[0]:SRB_342_732;}
show -design_net {_N101}
show -design_net {_N188}
unroute -branch {_N188:M2:CLMA_357_546;}
manual_route -net {_N188} -branch {M2:CLMA_357_546} -pins {ZDNE[0]:SRB_300_402>IDNE[0]:SRB_306_408>ZDNE[2]:SRB_306_570>IDNE[2]:SRB_312_576;}
show -design_net {_N188}
show -design_net {_N78}
unroute -branch {_N78:TX_DATA[1]:IOLHR_364_834;}
manual_route -net {_N78} -branch {TX_DATA[1]:IOLHR_364_834} -pins {ZDNE[0]:SRB_342_816>IDNE[0]:SRB_348_822;}
show -design_net {_N78}
save_adif
file copy {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera-vga-output/physical-hold-20261031-b/input.adf} {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera-vga-output/physical-hold-20261031-b/pre-sta.adf}
mpnr_report_timing -force_to_run -delay_type min_max -max_path 1000 -nworst 4 -report_exception TRUE
.switch_db -route -input {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera-vga-output/physical-hold-20261031-b/input.adf} -output {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera-vga-output/physical-hold-20261031-b/route-dump.txt}
puts {CAMERA_EXACT_PHYSICAL_REPAIR_COMPLETE}
flush stdout
}
