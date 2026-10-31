set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676
add_design {P:/distortion/build/processed-output/physical-tx-common-20261031-a/dummy.v}
if {[info script] ne {}} {
    mpnr -input {P:/distortion/build/processed-output/physical-tx-common-20261031-a/input.adf}
    puts {TX_COMMON_G0_MIN_FAST_RISE}
    get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {g_out[0]} -min -fast -max_path 8
    puts {TX_COMMON_G0_MIN_FAST_FALL}
    get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -fall_to {g_out[0]} -min -fast -max_path 8
    puts {TX_COMMON_CLOCK_MIN_FAST_RISE}
    get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {pix_clk} -min -fast -max_path 8
    puts {TX_COMMON_G0_MAX_SLOW_RISE}
    get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {g_out[0]} -max_path 8
    puts {TX_COMMON_G0_CLK_MIN_FAST_RISE}
    get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/g[0]/opit_0_L8Q_perm/CLK} -min -fast -max_path 8

    puts {PROCESSED_PHYSICAL_STAGE_COMPLETE}
    flush stdout
}
