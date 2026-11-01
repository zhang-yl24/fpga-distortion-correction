set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera720-output/hold-route-a/dummy.v}
if {[info script] ne {}} {
    mpnr -input {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera720-output/hold-route-a/input.adf}
show -design_net {_N50}
unroute -branch {_N50:A4:CLMA_171_678;}
manual_route -net {_N50} -branch {A4:CLMA_171_678} -pins {ZDNE[0]:SRB_150_660>IDNE[0]:SRB_156_666;}
show -design_net {_N50}
show -design_net {_N50}
unroute -branch {_N50:C4:CLMS_171_673;}
manual_route -net {_N50} -branch {C4:CLMS_171_673} -pins {ZDNE[1]:SRB_150_660>IDNE[1]:SRB_156_666;}
show -design_net {_N50}
    save_adif
    file copy {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera720-output/hold-route-a/input.adf} {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera720-output/hold-route-a/saved-route.adf}
    .switch_db -route -input {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera720-output/hold-route-a/input.adf} -output {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera720-output/hold-route-a/route-dump.txt}
    puts {CAMERA720_MEASURED_HOLD_ROUTES_SAVED}
    flush stdout
}
