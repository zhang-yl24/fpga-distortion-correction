set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera-vga-output/physical-query-20261031-a/dummy.v}
if {[info script] ne {}} {
    mpnr -input {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera-vga-output/physical-query-20261031-a/input.adf}
puts {CAMERA_BASELINE_HOLD_ROUTES}
show -design_net {_N101}
show -design_net {_N188}
show -design_net {_N78}
show -dev_instance {CLMS_345_769;CLMA_351_774;CLMS_351_439;CLMA_357_546;CLMA_357_841;IOLHR_364_834}
.switch_db -route -input {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera-vga-output/physical-query-20261031-a/input.adf} -output {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera-vga-output/physical-query-20261031-a/route-dump.txt}
file copy {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera-vga-output/physical-query-20261031-a/input.adf} {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera-vga-output/physical-query-20261031-a/pre-sta.adf}
mpnr_report_timing -force_to_run -delay_type min_max -max_path 1000 -nworst 4 -report_exception TRUE
mpnr_report_timing -help
manual_route -help
.show_wire -help

    puts {CAMERA_PHYSICAL_QUERY_COMPLETE}
    flush stdout
}
