set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676
add_design {P:/distortion/build/processed-output/physical-tx-probe-20261031-a/dummy.v}
if {[info script] ne {}} {
    mpnr -input {P:/distortion/build/processed-output/physical-tx-probe-20261031-a/input.adf}
    report_path_timing -help
    get_path_delay -help
    puts {TX_G0_MIN_FAST}
    get_path_delay -from {system/output_video/g[0]/opit_0_L8Q_perm/CLK} -to {g_out[0]} -min -fast -max_path 8
    puts {TX_CLOCK_MIN_FAST}
    get_path_delay -from {video_pll/u_gpll/gpll_inst/CLKOUT0} -to {pix_clk} -min -fast -max_path 8

    puts {PROCESSED_PHYSICAL_STAGE_COMPLETE}
    flush stdout
}
