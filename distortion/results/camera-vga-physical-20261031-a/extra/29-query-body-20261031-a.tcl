puts {CAMERA_BASELINE_HOLD_ROUTES}
show -design_net {_N101}
show -design_net {_N188}
show -design_net {_N78}
show -dev_instance {CLMS_345_769;CLMA_351_774;CLMS_351_439;CLMA_357_546;CLMA_357_841;IOLHR_364_834}
.switch_db -route -input {@WORK@/input.adf} -output {@WORK@/route-dump.txt}
file copy {@WORK@/input.adf} {@WORK@/pre-sta.adf}
mpnr_report_timing -force_to_run -delay_type min_max -max_path 1000 -nworst 4 -report_exception TRUE
mpnr_report_timing -help
manual_route -help
.show_wire -help
