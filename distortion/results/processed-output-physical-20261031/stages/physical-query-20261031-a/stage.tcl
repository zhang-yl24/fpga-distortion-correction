set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676
add_design {P:/distortion/build/processed-output/physical-query-20261031-a/dummy.v}
if {[info script] ne {}} {
    mpnr -input {P:/distortion/build/processed-output/physical-query-20261031-a/input.adf}
    puts {PROCESSED_ORIGINAL_HOLD_ROUTE}
    show -design_net {_N107}
    show -dev_instance {CLMA_345_852;CLMS_339_847;IOLHR_364_858}
    mpnr_report_timing -force_to_run -delay_type min_max -max_path 1000 -nworst 4 -report_exception TRUE
    gen_netlist -force_to_run -input_db_file {P:/distortion/build/processed-output/physical-query-20261031-a/input.adf} -func_sim_only

    puts {PROCESSED_PHYSICAL_STAGE_COMPLETE}
    flush stdout
}
