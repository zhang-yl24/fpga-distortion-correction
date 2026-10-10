set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676
report_timing -force_to_run -input_db_file {D:/English/FPGA/distortion/build/corrected_video/place_route/corrected_video_pnr.adf} -delay_type min -from [get_clocks phy_dq_sysclk_1] -to [get_clocks ddrphy_sysclk] -max_path 5
