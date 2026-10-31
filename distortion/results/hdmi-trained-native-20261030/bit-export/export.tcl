add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/build/hdmi-uart-diagnostic/trained-pds-1030-a/frozen-inputs/board/hdmi_uart_trained_diag.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/build/hdmi-uart-diagnostic/trained-pds-1030-a/frozen-inputs/rtl/experimental/hdmi_diag_uart.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/build/hdmi-uart-diagnostic/trained-pds-1030-a/frozen-inputs/rtl/uart_tx.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/build/hdmi-uart-diagnostic/trained-pds-1030-a/frozen-inputs/rtl/experimental/ms72xx_ready_observed_ctl.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/build/hdmi-uart-diagnostic/trained-pds-1030-a/frozen-inputs/rtl/experimental/ms7200_1080p30_ready_ctl.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/build/hdmi-uart-diagnostic/trained-pds-1030-a/frozen-inputs/rtl/experimental/ms7210_checked_ctl.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/build/hdmi-uart-diagnostic/trained-pds-1030-a/frozen-inputs/rtl/experimental/iic_dri_checked.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/build/hdmi-uart-diagnostic/trained-pds-1030-a/frozen-inputs/rtl/experimental/hdmi1080_input_status_trained.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/build/hdmi-uart-diagnostic/trained-pds-1030-a/frozen-inputs/rtl/experimental/dvp_mode_admission_monitor_cdc.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/build/hdmi-uart-diagnostic/trained-pds-1030-a/frozen-inputs/platform/video_base/ipcore/cfg_pll/cfg_pll.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/build/hdmi-uart-diagnostic/trained-pds-1030-a/frozen-inputs/board/bringup_pll.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/build/hdmi-uart-diagnostic/trained-pds-1030-a/frozen-inputs/rtl/video_pattern.v}
add_constraint {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/build/hdmi-uart-diagnostic/trained-pds-1030-a/hdmi_uart_diag.fdc}
set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676
compile -top_module hdmi_uart_trained_diag
synthesize -ads -selected_syn_tool_opt 2
dev_map
pnr -optimize_multi_corner_timing -fix_hold_violation -fix_hold_violation_iterations 50 -fix_hold_violation_threshold 100 -fix_hold_violation_in_route TRUE
report_timing -force_to_run -input_db_file {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/build/hdmi-uart-diagnostic/trained-bit-1030-a/audited-final.adf} -delay_type min_max -max_path 1000 -nworst 1 -report_exception TRUE
if {[info script] ne {}} {
 set checked [exec {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/.venv/Scripts/python.exe} {C:/Users/31641/.codex/visualizations/2026/10/30/01a18b10-3666-7ef2-85f5-5a3db14eb3d0/run_trained_bitstream.py} --audit]
 puts $checked
 if {[string first {TRAINED_PRE_BIT_PASS 88a6d04e25fa6de3d280d1458a06ef2ded506f1b6768476ae94dc7ce45fab399} $checked] < 0} {error {native gate did not pass}}
 gen_bit_stream -force_to_run -input_db_file {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/build/hdmi-uart-diagnostic/trained-bit-1030-a/audited-final.adf} -scbv {High Voltage} -unused_io_status UNUSED
 puts {TRAINED_BITSTREAM_COMPLETE}
 flush stdout
}
