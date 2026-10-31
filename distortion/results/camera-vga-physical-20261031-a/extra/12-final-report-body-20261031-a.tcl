file copy {@WORK@/input.adf} {@WORK@/pre-sta.adf}
mpnr_report_timing -force_to_run -delay_type min_max -max_path 1000 -nworst 4 -report_exception TRUE
.switch_db -route -input {@WORK@/input.adf} -output {@WORK@/route-dump.txt}
puts {CAMERA_EXACT__N78}
report_path_timing -delay_type min_max -max_path 100 -nworst 8 -report_exception TRUE -from {u_ddr3_test_h/u_ddrphy_top/ddrphy_dfi/phy_wrdata_d[3]/opit_0_inv_L6Q_LUT6DQL5Q_perm/CLK} -to {u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/i_dqs_group[0].ddrphy_data_slice/dq_loop[1].u_iobuf_dq/opit_1/TX_DATA[1]}
puts {CAMERA_EXACT__N188}
report_path_timing -delay_type min_max -max_path 100 -nworst 8 -report_exception TRUE -from {u_ddr3_test_h/u_ddrphy_top/ddrphy_dll_update_ctrl/dll_update_n/opit_0_inv_L6Q_LUT6DQL5Q_perm/CLK} -to {u_ddr3_test_h/u_ddrphy_top/u_dll_update_n_sync/sig_async_r1[0]/opit_0_inv_srl/D}
puts {CAMERA_EXACT__N101}
report_path_timing -delay_type min_max -max_path 100 -nworst 8 -report_exception TRUE -from {u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/i_dqs_group[0].ddrphy_data_slice/dq_loop[2].u_iobuf_dq/opit_1/ICLKDIV} -to {u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/i_dqs_group[0].ddrphy_data_slice/ddrphy_dqs_rddata_align/rddata_r1[21]/opit_0_inv_srl/D}
