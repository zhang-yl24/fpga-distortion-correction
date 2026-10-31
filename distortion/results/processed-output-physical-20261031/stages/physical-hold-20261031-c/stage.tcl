set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676
add_design {P:/distortion/build/processed-output/physical-hold-20261031-c/dummy.v}
if {[info script] ne {}} {
    mpnr -input {P:/distortion/build/processed-output/physical-hold-20261031-c/input.adf}
    .show_wire -help
    show_device -help
    report_region -help
    puts {PROCESSED_HOLD_ORIGINAL_ROUTE}
    show -design_net {_N107}
    unroute -branch {_N107:M3:CLMS_339_847;}
    manual_route -net {_N107} -branch {M3:CLMS_339_847} -pins {ZDNE[1]:SRB_342_816>IDNE[1]:SRB_348_822;}
    puts {PROCESSED_HOLD_MODIFIED_ROUTE}
    show -design_net {_N107}
    save_adif

    puts {PROCESSED_PHYSICAL_STAGE_COMPLETE}
    flush stdout
}
