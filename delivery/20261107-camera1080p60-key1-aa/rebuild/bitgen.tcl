source [file join [file dirname [info script]] physical.tcl]
checked BITGEN [list gen_bit_stream -force_to_run -input_db_file [checkpoint] -create_bit_file TRUE]
