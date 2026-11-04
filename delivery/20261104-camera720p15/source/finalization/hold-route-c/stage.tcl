set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera720-view-toggle/hold-route-c/dummy.v}
if {[info script] ne {}} {
    mpnr -input {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera720-view-toggle/hold-route-c/input.adf}
    mpnr_report_timing -force_to_run -delay_type min_max -max_path 1000 -nworst 4 -report_exception TRUE
    file copy {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera720-view-toggle/hold-route-c/input.adf} {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera720-view-toggle/hold-route-c/post-init.adf}
show -design_net {_N74}
unroute -branch {_N74:TX_DATA[5]:IOLHR_364_834;}
manual_route -net {_N74} -branch {TX_DATA[5]:IOLHR_364_834} -pins {ZDNE[0]:SRB_318_792>IDNE[0]:SRB_324_798;}
show -design_net {_N74}
show -design_net {_N138}
unroute -branch {_N138:M1:CLMA_357_697;}
manual_route -net {_N138} -branch {M1:CLMA_357_697} -pins {ZDNE[2]:SRB_336_666>IDNE[2]:SRB_342_672;}
show -design_net {_N138}
    save_adif
    file copy {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera720-view-toggle/hold-route-c/input.adf} {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera720-view-toggle/hold-route-c/saved-route.adf}
    .switch_db -route -input {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera720-view-toggle/hold-route-c/input.adf} -output {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera720-view-toggle/hold-route-c/route-dump.txt}
    puts {CAMERA720_VIEW_TOGGLE_HOLD_ROUTE_SAVED}
    flush stdout
}
