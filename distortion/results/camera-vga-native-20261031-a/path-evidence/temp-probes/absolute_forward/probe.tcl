puts "CODEX_PATH_PROBE_BEGIN"
puts [list CWD [pwd]]
puts [list SCRIPT [info script]]
puts [list LOCAL_READABLE [file readable {probe.tcl}]]
puts [list ABS_READABLE [file readable {C:/Users/31641/AppData/Local/Temp/codex-camera-vga-output/path-probe-20261031-c/absolute_forward/probe.tcl}]]
puts [list ORIGINAL_READABLE [file readable {C:/Users/31641/AppData/Local/Temp/codex-camera-vga-output/pds-a/timing.tcl}]]
puts "CODEX_PATH_PROBE_END"
