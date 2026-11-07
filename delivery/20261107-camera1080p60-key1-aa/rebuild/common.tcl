# Relative paths only. This file never selects license files or hardware.
set ::rebuild_dir [file dirname [file normalize [info script]]]
if {![info exists ::env(REPRO_ROOT)]} {error "Run through run_build.py with a complete source tree"}
set ::repo_root [file normalize $::env(REPRO_ROOT)]
proc repo {relative} {return [file join $::repo_root $relative]}
proc checked {label command} {
    puts "BEGIN $label"
    set rc [catch {uplevel 1 $command} result options]
    if {$rc != 0} {return -options $options $result}
    puts "END $label"
    return $result
}
proc checkpoint {} {
    if {![info exists ::env(REPRO_INPUT_ADF)]} {error "Missing explicit input checkpoint"}
    set p [file normalize $::env(REPRO_INPUT_ADF)]
    if {![file isfile $p]} {error "Input checkpoint does not exist"}
    return $p
}
set f [open [file join $::rebuild_dir source-list.txt] r]
set expected [split [string trim [read $f]] "\n"]
close $f
set missing {}
foreach name $expected {if {![file isfile [repo $name]]} {lappend missing $name}}
if {[llength $missing]} {error "STOP: missing source inputs: $missing"}
