set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676
add_design {P:/distortion/build/processed-output/physical-cdc-interstage-20261031-a/dummy.v}
if {[info script] ne {}} {
    mpnr -input {P:/distortion/build/processed-output/physical-cdc-interstage-20261031-a/input.adf}
    file copy {P:/distortion/build/processed-output/physical-cdc-interstage-20261031-a/input.adf} {P:/distortion/build/processed-output/physical-cdc-interstage-20261031-a/pre-sta.adf}
    puts {CDC_NONLOCAL_INTERSTAGE_BEGIN}
    report_path_timing -delay_type min_max -max_path 100 -nworst 8 -report_exception TRUE -from {ddr_ready_ref[0]/opit_0_L6Q_perm/CLK system_failed_ref[0]/opit_0_L6Q_LUT6DQL5Q_perm/CLK} -to {system_failed_ref[1]/opit_0_L6Q_LUT6DQL5Q_perm/I2 system_failed_ref[1]/opit_0_L6Q_LUT6DQL5Q_perm/I4 processed_bit_ref[1]/opit_0_L6Q_LUT6DQL5Q_perm/I4}
    puts {CDC_NONLOCAL_INTERSTAGE_END}

    puts {PROCESSED_PHYSICAL_STAGE_COMPLETE}
    flush stdout
}
