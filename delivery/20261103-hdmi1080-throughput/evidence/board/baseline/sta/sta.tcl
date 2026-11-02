proc checked {command} {
  set rc [catch {uplevel 1 $command} result]
  if {$rc != 0} { puts stderr $result; exit 1 }
  puts $result
}
cd {D:/fpga-build/baseline-final/stages/sta}
checked [list set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676]
checked [list add_design {D:/fpga-build/baseline-final/stages/sta/dummy.v}]
checked [list add_constraint {D:/fpga-build/baseline-final/native/source/build/offline-20261024/boardtop-penn-prep-20261029-a/board1080-diagnostic.fdc}]
checked [list add_constraint {D:/fpga-build/baseline-final/uart-pins.fdc}]
checked [list add_constraint {D:/fpga-build/baseline-final/stages/map/prj_tasks/pnr_1/device_map/board1080_top.pcf} -pnr_set pnr_1]
puts {EXPLICIT_FROZEN_FDC_UART_OVERLAY_AND_MAP_PCF_LOADED}
checked [list report_timing -force_to_run -input_db_file {D:/fpga-build/baseline-final/stages/route/prj_tasks/pnr_1/place_route/board1080_top_pnr.adf} -delay_type min_max -max_path 50 -nworst 4 -report_exception TRUE -report_io_datasheet]
puts {BOARD_STA_STAGE_COMPLETE}
