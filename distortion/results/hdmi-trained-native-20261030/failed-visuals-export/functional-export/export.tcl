add_design {C:/Users/31641/.codex/visualizations/2026/10/30/01a18b10-3666-7ef2-85f5-5a3db14eb3d0/trained-review-1030-a/functional-export/sources/board/hdmi_uart_trained_diag.v}
add_design {C:/Users/31641/.codex/visualizations/2026/10/30/01a18b10-3666-7ef2-85f5-5a3db14eb3d0/trained-review-1030-a/functional-export/sources/rtl/experimental/hdmi_diag_uart.v}
add_design {C:/Users/31641/.codex/visualizations/2026/10/30/01a18b10-3666-7ef2-85f5-5a3db14eb3d0/trained-review-1030-a/functional-export/sources/rtl/uart_tx.v}
add_design {C:/Users/31641/.codex/visualizations/2026/10/30/01a18b10-3666-7ef2-85f5-5a3db14eb3d0/trained-review-1030-a/functional-export/sources/rtl/experimental/ms72xx_ready_observed_ctl.v}
add_design {C:/Users/31641/.codex/visualizations/2026/10/30/01a18b10-3666-7ef2-85f5-5a3db14eb3d0/trained-review-1030-a/functional-export/sources/rtl/experimental/ms7200_1080p30_ready_ctl.v}
add_design {C:/Users/31641/.codex/visualizations/2026/10/30/01a18b10-3666-7ef2-85f5-5a3db14eb3d0/trained-review-1030-a/functional-export/sources/rtl/experimental/ms7210_checked_ctl.v}
add_design {C:/Users/31641/.codex/visualizations/2026/10/30/01a18b10-3666-7ef2-85f5-5a3db14eb3d0/trained-review-1030-a/functional-export/sources/rtl/experimental/iic_dri_checked.v}
add_design {C:/Users/31641/.codex/visualizations/2026/10/30/01a18b10-3666-7ef2-85f5-5a3db14eb3d0/trained-review-1030-a/functional-export/sources/rtl/experimental/hdmi1080_input_status_trained.v}
add_design {C:/Users/31641/.codex/visualizations/2026/10/30/01a18b10-3666-7ef2-85f5-5a3db14eb3d0/trained-review-1030-a/functional-export/sources/rtl/experimental/dvp_mode_admission_monitor_cdc.v}
add_design {C:/Users/31641/.codex/visualizations/2026/10/30/01a18b10-3666-7ef2-85f5-5a3db14eb3d0/trained-review-1030-a/functional-export/sources/platform/video_base/ipcore/cfg_pll/cfg_pll.v}
add_design {C:/Users/31641/.codex/visualizations/2026/10/30/01a18b10-3666-7ef2-85f5-5a3db14eb3d0/trained-review-1030-a/functional-export/sources/board/bringup_pll.v}
add_design {C:/Users/31641/.codex/visualizations/2026/10/30/01a18b10-3666-7ef2-85f5-5a3db14eb3d0/trained-review-1030-a/functional-export/sources/rtl/video_pattern.v}
add_constraint {C:/Users/31641/.codex/visualizations/2026/10/30/01a18b10-3666-7ef2-85f5-5a3db14eb3d0/trained-review-1030-a/functional-export/context.fdc}
set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676
compile -top_module hdmi_uart_trained_diag
synthesize -ads -selected_syn_tool_opt 2
dev_map
pnr -optimize_multi_corner_timing -fix_hold_violation -fix_hold_violation_iterations 50 -fix_hold_violation_threshold 100 -fix_hold_violation_in_route TRUE
report_timing -force_to_run -input_db_file {C:/Users/31641/.codex/visualizations/2026/10/30/01a18b10-3666-7ef2-85f5-5a3db14eb3d0/trained-review-1030-a/functional-export/input.adf} -delay_type min_max -max_path 5
if {[info script] ne {}} {
 gen_netlist -force_to_run -input_db_file {C:/Users/31641/.codex/visualizations/2026/10/30/01a18b10-3666-7ef2-85f5-5a3db14eb3d0/trained-review-1030-a/functional-export/input.adf} -func_sim_only
 puts {TRAINED_FUNCTIONAL_EXPORT_COMPLETE}
 flush stdout
}
