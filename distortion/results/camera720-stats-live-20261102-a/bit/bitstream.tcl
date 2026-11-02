# Independent 720p transport compile/map/route/STA; no bitstream or hardware.
set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera720-stats-delay/build-c/compiled/rtl/mul32_pipe.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera720-stats-delay/build-c/compiled/rtl/pixel_inverse_rotation.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera720-stats-delay/build-c/compiled/rtl/bounded_brown_inverse_mapper.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera720-stats-delay/build-c/compiled/rtl/bilinear_rgb.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera720-stats-delay/build-c/compiled/rtl/video_async_fifo.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera720-stats-delay/build-c/compiled/rtl/ddr_read_arbiter.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera720-stats-delay/build-c/compiled/rtl/ddr_write_arbiter.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera720-stats-delay/build-c/compiled/rtl/ddr_video_reader.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera720-stats-delay/build-c/compiled/rtl/experimental/ddr_adaptive_result_writer.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera720-stats-delay/build-c/compiled/rtl/experimental/adaptive_gamma_stream.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera720-stats-delay/build-c/compiled/rtl/experimental/adaptive_gamma_tagged.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera720-stats-delay/build-c/compiled/rtl/experimental/ddr_neighbour_cache_scatter4_rowpipe.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera720-stats-delay/build-c/compiled/rtl/experimental/ddr_remap_sample_scatter4_rowpipe.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera720-stats-delay/build-c/compiled/rtl/experimental/rotated_remap_core_gamma_scatter4.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera720-stats-delay/build-c/compiled/rtl/experimental/pipeline_gamma_frame_engine_1080_scatter4.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera720-stats-delay/build-c/compiled/rtl/experimental/lens1080_bank_core.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera720-stats-delay/build-c/compiled/rtl/experimental/ddr_video_output_1080_board.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera720-stats-delay/build-c/compiled/platform/video_base/ipcore/ddr3_test/ddr3_test.idf}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera720-stats-delay/build-c/compiled/board/bringup_pll.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera720-stats-delay/build-c/compiled/board/hdmi_tx_init.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera720-stats-delay/build-c/compiled/rtl/reg16_i2c.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera720-stats-delay/build-c/compiled/board/camera720_calibrated_stats_delay_top.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera720-stats-delay/build-c/compiled/rtl/experimental/dvp_rgb565_capture_cdc.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera720-stats-delay/build-c/compiled/rtl/experimental/camera_vga_input_dma.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera720-stats-delay/build-c/compiled/rtl/experimental/camera_vga_input_write_link.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera720-stats-delay/build-c/compiled/rtl/experimental/camera_vga_video_system.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera720-stats-delay/build-c/compiled/rtl/experimental/ov5640_current720_init.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera720-stats-delay/build-c/compiled/rtl/experimental/capture_warmup.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera720-stats-delay/build-c/compiled/rtl/experimental/raw_camera_input_delay.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera720-stats-delay/build-c/compiled/rtl/experimental/ov5640_current720_frontend.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera720-stats-delay/build-c/compiled/rtl/experimental/dvp_mode_admission_monitor.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera720-stats-delay/build-c/compiled/rtl/experimental/camera720_core_stats_uart.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera720-stats-delay/build-c/compiled/rtl/uart_tx.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera720-stats-delay/build-c/compiled/rtl/experimental/raw_camera_control_input_delay.v}
add_constraint {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera720-stats-delay/build-c/compiled/board/camera720-calibrated-stats-delay.fdc}
compile -top_module camera720_calibrated_stats_delay_top
synthesize -ads -selected_syn_tool_opt 2
dev_map
add_constraint {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera720-stats-delay/build-c/compiled/board/board1080-ddr-ioclk-priority.rcf}
pnr -optimize_multi_corner_timing -fix_hold_violation
report_timing -force_to_run -input_db_file {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera720-stats-delay/bit-c2/audited-final.adf} -delay_type min_max -max_path 1000 -nworst 4 -report_exception TRUE
if {[info script] ne {}} {
    set checked [exec {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/.venv/Scripts/python.exe} -B {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/tools/camera720_stats_delay_bitstream.py} --gate {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera720-stats-delay/bit-c2}]
    puts $checked
    if {[string first {CAMERA720_CALIBRATED_STATS_DELAY_GATE_PASS 29e2e519cdb7e27ca43209dd57761bd8e70d2e761decbfebf96f5167b311e19e} $checked] < 0} {error {Missing 720p pre-bit gate}}
    gen_bit_stream -force_to_run -input_db_file {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera720-stats-delay/bit-c2/audited-final.adf} -scbv {High Voltage} -unused_io_status UNUSED
    puts {CAMERA720_CALIBRATED_STATS_DELAY_BITSTREAM_COMPLETE}
    flush stdout
}
