set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera720-output/query-a/dummy.v}
if {[info script] ne {}} {
    mpnr -input {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera720-output/query-a/input.adf}
    mpnr_report_timing -force_to_run -delay_type min_max -max_path 1000 -nworst 4 -report_exception TRUE
puts {CAMERA720_NATIVE_CLOCKS}
get_clocks -regexp {.*}
puts {CAMERA720_NATIVE_PORTS}
get_ports -regexp {.*}
puts {CAMERA720_NATIVE_MONITOR_PINS}
get_pins -hierarchical -regexp {^camera_configuration/monitor/.*}
puts {CAMERA720_NATIVE_BOARD_RESET_PINS}
get_pins -hierarchical -regexp {^(power_ready|key_reset_sync|ref_reset|core_reset|board_failed_core).*}
.switch_db -route -input {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera720-output/query-a/input.adf} -output {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera720-output/query-a/route-dump.txt}
    puts {CAMERA720_OUTPUT_INSPECTION_COMPLETE}
    flush stdout
}
