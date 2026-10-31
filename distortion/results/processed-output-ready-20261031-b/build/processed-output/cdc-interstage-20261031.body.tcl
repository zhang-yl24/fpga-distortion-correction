    file copy {@WORK@/input.adf} {@WORK@/pre-sta.adf}
    puts {CDC_NONLOCAL_INTERSTAGE_BEGIN}
    report_path_timing -delay_type min_max -max_path 100 -nworst 8 -report_exception TRUE -from {ddr_ready_ref[0]/opit_0_L6Q_perm/CLK system_failed_ref[0]/opit_0_L6Q_LUT6DQL5Q_perm/CLK} -to {system_failed_ref[1]/opit_0_L6Q_LUT6DQL5Q_perm/I2 system_failed_ref[1]/opit_0_L6Q_LUT6DQL5Q_perm/I4 processed_bit_ref[1]/opit_0_L6Q_LUT6DQL5Q_perm/I4}
    puts {CDC_NONLOCAL_INTERSTAGE_END}
