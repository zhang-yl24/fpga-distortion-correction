source [file join [file dirname [info script]] physical.tcl]
checked INDEPENDENT_STA [list report_timing -force_to_run -input_db_file [checkpoint] -delay_type min_max -max_path 10000 -slack_less_than 0 -nworst 1 -report_exception TRUE -report_max_skew]
