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
report_timing -force_to_run -delay_type min_max -max_path 20
