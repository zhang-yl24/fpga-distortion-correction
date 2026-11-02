set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera720-view-toggle/hold-query-a/dummy.v}
if {[info script] ne {}} {
    mpnr -input {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera720-view-toggle/hold-query-a/input.adf}
    mpnr_report_timing -force_to_run -delay_type min_max -max_path 1000 -nworst 4 -report_exception TRUE
puts {VIEW_HOLD_1_0}
report_path_timing -delay_type min_max -max_path 1000 -nworst 8 -report_exception TRUE -from {t:u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/i_dqs_group[0].ddrphy_data_slice/ddrphy_dqs_rddata_align/ck_dqs_diff[0]/opit_0_inv_L6Q_LUT6DQL5Q_perm/CLK} -through {t:u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/i_dqs_group[0].ddrphy_data_slice/ddrphy_dqs_rddata_align/ck_dqs_diff[0]/opit_0_inv_L6Q_LUT6DQL5Q_perm/L5Q} -to {t:u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/i_dqs_group[0].ddrphy_data_slice/dq_loop[1].u_iobuf_dq/opit_1/TX_DATA[5]}
puts {VIEW_HOLD_1_1}
report_path_timing -delay_type min_max -max_path 1000 -nworst 8 -report_exception TRUE -from {t:u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/i_dqs_group[0].ddrphy_data_slice/ddrphy_dqs_rddata_align/ck_dqs_diff[0]/opit_0_inv_L6Q_LUT6DQL5Q_perm/CLK} -through {t:u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/i_dqs_group[0].ddrphy_data_slice/ddrphy_dqs_rddata_align/ck_dqs_diff[0]/opit_0_inv_L6Q_LUT6DQL5Q_perm/L6Q} -to {t:u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/i_dqs_group[0].ddrphy_data_slice/dq_loop[1].u_iobuf_dq/opit_1/TX_DATA[5]}
show -design_net {_N74}
puts {VIEW_HOLD_2_0}
report_path_timing -delay_type min_max -max_path 1000 -nworst 8 -report_exception TRUE -from {t:u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/i_dqs_group[2].ddrphy_data_slice/dq_loop[4].u_iobuf_dq/opit_1/ICLKDIV} -through {t:u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/i_dqs_group[2].ddrphy_data_slice/dq_loop[4].u_iobuf_dq/opit_1/RX_DATA[7]} -to {t:u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/i_dqs_group[2].ddrphy_data_slice/ddrphy_dqs_rddata_align/rddata_r1[39]/opit_0_inv_srl/D}
show -design_net {_N138}
    puts {CAMERA720_VIEW_TOGGLE_INSPECTION_COMPLETE}
    flush stdout
}
