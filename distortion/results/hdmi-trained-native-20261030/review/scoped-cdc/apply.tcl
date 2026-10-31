set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/build/hdmi-uart-diagnostic/trained-review-1030-a/scoped-cdc/dummy.v}
if {[info script] ne {}} {
 mpnr -input {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/build/hdmi-uart-diagnostic/trained-review-1030-a/scoped-cdc/input.adf}
 source {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/build/hdmi-uart-diagnostic/trained-review-1030-a/scoped-cdc/scope.fdc}
 save_adif
 puts {TRAINED_SCOPED_CDC_SAVED}
 flush stdout
}
