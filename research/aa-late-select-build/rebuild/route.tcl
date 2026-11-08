source [file join [file dirname [info script]] physical.tcl]
checked ROUTE [list route -force_to_run -input_place_db_file [checkpoint]]
checked HOLD_OPTIMIZE [list route_optimize -force_to_run -fix_hold_violation_in_route TRUE -fix_hold_violation_threshold_for_clock_path_cross_srb 100 -fix_hold_violation_threshold_for_clk_tree 100]
