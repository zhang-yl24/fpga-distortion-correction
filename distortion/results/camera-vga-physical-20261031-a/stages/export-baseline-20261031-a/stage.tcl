# Independent diagnostic preparation only; no bitstream or hardware command.
set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera-vga-output/pds-20261031-a/compiled/rtl/mul32_pipe.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera-vga-output/pds-20261031-a/compiled/rtl/pixel_inverse_rotation.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera-vga-output/pds-20261031-a/compiled/rtl/bounded_brown_inverse_mapper.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera-vga-output/pds-20261031-a/compiled/rtl/bilinear_rgb.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera-vga-output/pds-20261031-a/compiled/rtl/video_async_fifo.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera-vga-output/pds-20261031-a/compiled/rtl/ddr_read_arbiter.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera-vga-output/pds-20261031-a/compiled/rtl/ddr_write_arbiter.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera-vga-output/pds-20261031-a/compiled/rtl/ddr_video_reader.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera-vga-output/pds-20261031-a/compiled/rtl/experimental/ddr_adaptive_result_writer.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera-vga-output/pds-20261031-a/compiled/rtl/experimental/adaptive_gamma_stream.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera-vga-output/pds-20261031-a/compiled/rtl/experimental/adaptive_gamma_tagged.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera-vga-output/pds-20261031-a/compiled/rtl/experimental/ddr_neighbour_cache_scatter4_rowpipe.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera-vga-output/pds-20261031-a/compiled/rtl/experimental/ddr_remap_sample_scatter4_rowpipe.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera-vga-output/pds-20261031-a/compiled/rtl/experimental/rotated_remap_core_gamma_scatter4.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera-vga-output/pds-20261031-a/compiled/rtl/experimental/pipeline_gamma_frame_engine_1080_scatter4.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera-vga-output/pds-20261031-a/compiled/rtl/experimental/lens1080_bank_core.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera-vga-output/pds-20261031-a/compiled/rtl/experimental/ddr_video_output_1080_board.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera-vga-output/pds-20261031-a/compiled/platform/video_base/ipcore/ddr3_test/ddr3_test.idf}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera-vga-output/pds-20261031-a/compiled/board/bringup_pll.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera-vga-output/pds-20261031-a/compiled/board/hdmi_tx_init.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera-vga-output/pds-20261031-a/compiled/rtl/reg16_i2c.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera-vga-output/pds-20261031-a/compiled/board/camera_vga_output_top.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera-vga-output/pds-20261031-a/compiled/rtl/experimental/dvp_rgb565_capture_cdc.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera-vga-output/pds-20261031-a/compiled/rtl/experimental/camera_vga_input_dma.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera-vga-output/pds-20261031-a/compiled/rtl/experimental/camera_vga_input_write_link.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera-vga-output/pds-20261031-a/compiled/rtl/experimental/camera_vga_video_system.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera-vga-output/pds-20261031-a/compiled/rtl/experimental/ov5640_cadence_trial_init.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera-vga-output/pds-20261031-a/compiled/rtl/experimental/capture_warmup.v}
add_constraint {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera-vga-output/pds-20261031-a/compiled/board/camera-vga-output-diagnostic.fdc}
compile -top_module camera_vga_output_top
synthesize -ads -selected_syn_tool_opt 2
dev_map
add_constraint {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera-vga-output/pds-20261031-a/compiled/board/board1080-ddr-ioclk-priority.rcf}
pnr -optimize_multi_corner_timing -fix_hold_violation
report_timing -force_to_run -input_db_file {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera-vga-output/export-baseline-20261031-a/input.adf} -delay_type min_max -max_path 1000 -nworst 4 -report_exception TRUE
if {[info script] ne {}} {
    gen_netlist -force_to_run -input_db_file {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera-vga-output/export-baseline-20261031-a/input.adf} -func_sim_only
    puts {CAMERA_FUNCTIONAL_EXPORT_COMPLETE}
    flush stdout
}
