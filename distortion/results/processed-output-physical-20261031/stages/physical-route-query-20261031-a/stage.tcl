set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676
add_design {P:/distortion/build/processed-output/physical-route-query-20261031-a/dummy.v}
if {[info script] ne {}} {
    mpnr -input {P:/distortion/build/processed-output/physical-route-query-20261031-a/input.adf}
    .switch_db -route -input {P:/distortion/build/processed-output/physical-route-query-20261031-a/input.adf} -output {P:/distortion/build/processed-output/physical-route-query-20261031-a/route-dump.txt}
    dump_net -grid_unit {SRB_342_816 SRB_342_822 SRB_348_822 SRB_348_828} -print_site -out_file {P:/distortion/build/processed-output/physical-route-query-20261031-a/waypoint-nets.txt}

    puts {PROCESSED_PHYSICAL_STAGE_COMPLETE}
    flush stdout
}
