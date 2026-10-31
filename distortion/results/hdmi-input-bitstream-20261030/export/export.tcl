add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/build/hdmi-uart-diagnostic/input-bit-1030-a/sources/board/hdmi_uart_input_diag.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/build/hdmi-uart-diagnostic/input-bit-1030-a/sources/rtl/experimental/hdmi_diag_uart.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/build/hdmi-uart-diagnostic/input-bit-1030-a/sources/rtl/uart_tx.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/build/hdmi-uart-diagnostic/input-bit-1030-a/sources/rtl/experimental/ms72xx_observed_ctl.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/build/hdmi-uart-diagnostic/input-bit-1030-a/sources/rtl/experimental/ms7200_1080p30_ctl.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/build/hdmi-uart-diagnostic/input-bit-1030-a/sources/rtl/experimental/ms7210_checked_ctl.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/build/hdmi-uart-diagnostic/input-bit-1030-a/sources/rtl/experimental/iic_dri_checked.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/build/hdmi-uart-diagnostic/input-bit-1030-a/sources/rtl/experimental/hdmi1080_input_status_cdc.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/build/hdmi-uart-diagnostic/input-bit-1030-a/sources/rtl/experimental/dvp_mode_admission_monitor_cdc.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/build/hdmi-uart-diagnostic/input-bit-1030-a/sources/platform/video_base/ipcore/cfg_pll/cfg_pll.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/build/hdmi-uart-diagnostic/input-bit-1030-a/sources/board/bringup_pll.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/build/hdmi-uart-diagnostic/input-bit-1030-a/sources/rtl/video_pattern.v}
add_constraint {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/build/hdmi-uart-diagnostic/input-bit-1030-a/context.fdc}
set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676
compile -top_module hdmi_uart_input_diag
synthesize -ads -selected_syn_tool_opt 2
dev_map
pnr -optimize_multi_corner_timing -fix_hold_violation -fix_hold_violation_iterations 50 -fix_hold_violation_threshold 100 -fix_hold_violation_in_route TRUE
report_timing -force_to_run -input_db_file {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/build/hdmi-uart-diagnostic/input-bit-1030-a/audited-final.adf} -delay_type min_max -max_path 1000 -nworst 1 -report_exception TRUE
if {[info script] ne {}} {
    set checked [exec {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/.venv/Scripts/python.exe} {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/tools/prepare_hdmi_input_bitstream.py} --audit-work {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/build/hdmi-uart-diagnostic/input-bit-1030-a}]
    puts $checked
    if {[string first {HDMI_INPUT_PRE_BIT_AUDIT_PASS d7858e4b705469e6619ba3c99df2c78bf47e2e4f515aeb3b328ea67c70c676a8} $checked] < 0} {error {Pre-bit audit marker absent}}
    gen_bit_stream -force_to_run -input_db_file {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/build/hdmi-uart-diagnostic/input-bit-1030-a/audited-final.adf} -scbv {High Voltage} -unused_io_status UNUSED
    puts {HDMI_INPUT_BITSTREAM_COMPLETE}
    flush stdout
}
