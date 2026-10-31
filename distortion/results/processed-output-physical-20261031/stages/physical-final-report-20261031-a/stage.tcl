set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676
add_design {P:/distortion/build/processed-output/physical-final-report-20261031-a/dummy.v}
if {[info script] ne {}} {
    mpnr -input {P:/distortion/build/processed-output/physical-final-report-20261031-a/input.adf}
    file copy {P:/distortion/build/processed-output/physical-final-report-20261031-a/input.adf} {P:/distortion/build/processed-output/physical-final-report-20261031-a/pre-sta.adf}
    show -design_net {_N107}
    mpnr_report_timing -force_to_run -delay_type min_max -max_path 1000 -nworst 4 -report_exception TRUE
    .switch_db -route -input {P:/distortion/build/processed-output/physical-final-report-20261031-a/input.adf} -output {P:/distortion/build/processed-output/physical-final-report-20261031-a/route-dump.txt}

    puts {PROCESSED_PHYSICAL_STAGE_COMPLETE}
    flush stdout
}
