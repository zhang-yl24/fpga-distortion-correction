set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera720-calibrated/final-report-a/dummy.v}
if {[info script] ne {}} {
    mpnr -input {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera720-calibrated/final-report-a/input.adf}
    mpnr_report_timing -force_to_run -delay_type min_max -max_path 1000 -nworst 4 -report_exception TRUE
    .switch_db -route -input {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera720-calibrated/final-report-a/input.adf} -output {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera720-calibrated/final-report-a/route-dump.txt}
    puts {CAMERA720_CALIBRATED_FINAL_INSPECTION_COMPLETE}
    flush stdout
}
