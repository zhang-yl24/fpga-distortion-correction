set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera-vga-output/physical-final-target-20261031-a/dummy.v}
if {[info script] ne {}} {
    mpnr -input {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera-vga-output/physical-final-target-20261031-a/input.adf}
mpnr_report_timing -force_to_run -delay_type min_max -max_path 20 -nworst 4 -report_exception TRUE
report_path_timing -delay_type min_max -max_path 100 -nworst 8 -report_exception TRUE -from {u_ddr3_test_h/u_ddrphy_top/ddrphy_dfi/phy_wrdata_d[3]/opit_0_inv_L6Q_LUT6DQL5Q_perm/CLK} -to {u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/i_dqs_group[0].ddrphy_data_slice/dq_loop[1].u_iobuf_dq/opit_1/TX_DATA[1]}

    puts {CAMERA_PHYSICAL_QUERY_COMPLETE}
    flush stdout
}
