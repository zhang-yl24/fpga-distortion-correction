set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676
add_design {P:/distortion/work/hdmi-camera-fisheye-tile8df8-20261103-a/route-scoped-v3-a/dummy.v}
if {[info script] ne {}} {
    mpnr -input {P:/distortion/work/hdmi-camera-fisheye-tile8df8-20261103-a/route-scoped-v3-a/input.adf}
    mpnr_report_timing -force_to_run -delay_type min_max -max_path 10000 -nworst 4 -report_exception TRUE
.switch_db -route -input {P:/distortion/work/hdmi-camera-fisheye-tile8df8-20261103-a/route-scoped-v3-a/input.adf} -output {P:/distortion/work/hdmi-camera-fisheye-tile8df8-20261103-a/route-scoped-v3-a/route-dump.txt}
    puts {HDMI_CAMERA_FISHEYE_TILE8DF8V3_SCOPED_NATIVE_INSPECTION_COMPLETE}
    flush stdout
}
