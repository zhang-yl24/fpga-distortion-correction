# Static helper only: no commands are invoked by this file.
# A later admitted script must call checked with a complete command as a list.
proc checked {label command} {
    puts "SENTINEL_BEGIN $label COMMAND=$command"
    flush stdout
    set rc [catch {uplevel 1 $command} result options]
    puts "SENTINEL_RESULT $label RC=$rc RESULT=$result OPTIONS=$options"
    if {$rc != 0} {
        if {[dict exists $options -errorinfo]} {
            puts "SENTINEL_ERRORINFO $label [dict get $options -errorinfo]"
        }
        if {[dict exists $options -errorcode]} {
            puts "SENTINEL_ERRORCODE $label [dict get $options -errorcode]"
        }
        flush stdout
        exit 1
    }
    flush stdout
    return $result
}
