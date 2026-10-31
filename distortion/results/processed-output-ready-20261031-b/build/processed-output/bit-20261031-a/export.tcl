# Independent diagnostic preparation only; no bitstream or hardware command.
set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676
add_design {P:/distortion/build/processed-output/pds-20261031-a/compiled/rtl/mul32_pipe.v}
add_design {P:/distortion/build/processed-output/pds-20261031-a/compiled/rtl/pixel_inverse_rotation.v}
add_design {P:/distortion/build/processed-output/pds-20261031-a/compiled/rtl/bounded_brown_inverse_mapper.v}
add_design {P:/distortion/build/processed-output/pds-20261031-a/compiled/rtl/bilinear_rgb.v}
add_design {P:/distortion/build/processed-output/pds-20261031-a/compiled/rtl/video_async_fifo.v}
add_design {P:/distortion/build/processed-output/pds-20261031-a/compiled/rtl/ddr_read_arbiter.v}
add_design {P:/distortion/build/processed-output/pds-20261031-a/compiled/rtl/ddr_write_arbiter.v}
add_design {P:/distortion/build/processed-output/pds-20261031-a/compiled/rtl/ddr_video_reader.v}
add_design {P:/distortion/build/processed-output/pds-20261031-a/compiled/rtl/experimental/ddr_adaptive_result_writer.v}
add_design {P:/distortion/build/processed-output/pds-20261031-a/compiled/rtl/experimental/adaptive_gamma_stream.v}
add_design {P:/distortion/build/processed-output/pds-20261031-a/compiled/rtl/experimental/adaptive_gamma_tagged.v}
add_design {P:/distortion/build/processed-output/pds-20261031-a/compiled/rtl/experimental/ddr_neighbour_cache_scatter4_rowpipe.v}
add_design {P:/distortion/build/processed-output/pds-20261031-a/compiled/rtl/experimental/ddr_remap_sample_scatter4_rowpipe.v}
add_design {P:/distortion/build/processed-output/pds-20261031-a/compiled/rtl/experimental/rotated_remap_core_gamma_scatter4.v}
add_design {P:/distortion/build/processed-output/pds-20261031-a/compiled/rtl/experimental/pipeline_gamma_frame_engine_1080_scatter4.v}
add_design {P:/distortion/build/processed-output/pds-20261031-a/compiled/rtl/experimental/lens1080_bank_core.v}
add_design {P:/distortion/build/processed-output/pds-20261031-a/compiled/rtl/experimental/hdmi1080_capture_cdc.v}
add_design {P:/distortion/build/processed-output/pds-20261031-a/compiled/rtl/experimental/hdmi1080_input_dma.v}
add_design {P:/distortion/build/processed-output/pds-20261031-a/compiled/rtl/experimental/hdmi1080_input_write_link.v}
add_design {P:/distortion/build/processed-output/pds-20261031-a/compiled/rtl/experimental/ddr_video_output_1080_board.v}
add_design {P:/distortion/build/processed-output/pds-20261031-a/compiled/rtl/experimental/hdmi1080_video_system_cdc_reset.v}
add_design {P:/distortion/build/processed-output/pds-20261031-a/compiled/platform/video_base/ipcore/ddr3_test/ddr3_test.idf}
add_design {P:/distortion/build/processed-output/pds-20261031-a/compiled/board/bringup_pll.v}
add_design {P:/distortion/build/processed-output/pds-20261031-a/compiled/board/processed_output_top.v}
add_design {P:/distortion/build/processed-output/pds-20261031-a/compiled/rtl/experimental/processed_output_pattern.v}
add_design {P:/distortion/build/processed-output/pds-20261031-a/compiled/board/hdmi_tx_init.v}
add_design {P:/distortion/build/processed-output/pds-20261031-a/compiled/rtl/reg16_i2c.v}
add_constraint {P:/distortion/build/processed-output/pds-20261031-a/compiled/board/processed-output-diagnostic.fdc}
compile -top_module processed_output_top
synthesize -ads -selected_syn_tool_opt 2
dev_map
add_constraint {P:/distortion/build/processed-output/pds-20261031-a/compiled/board/board1080-ddr-ioclk-priority.rcf}
pnr -optimize_multi_corner_timing -fix_hold_violation
report_timing -force_to_run -input_db_file {P:/distortion/build/processed-output/bit-20261031-a/audited-final.adf} -delay_type min_max -max_path 1000 -nworst 4 -report_exception TRUE
if {[info script] ne {}} {
    set checked [exec {P:/.venv/Scripts/python.exe} {P:/distortion/tools/processed_output_bitstream.py} --gate {P:/distortion/build/processed-output/bit-20261031-a}]
    puts $checked
    if {[string first {PROCESSED_OUTPUT_PRE_BIT_AUDIT_PASS 1d19936ede917ea1268a17a11fb3b0b34ff84753abefb062ae26d8a2c7c7550b} $checked] < 0} {error {Missing pre-bit gate}}
    gen_bit_stream -force_to_run -input_db_file {P:/distortion/build/processed-output/bit-20261031-a/audited-final.adf} -scbv {High Voltage} -unused_io_status UNUSED
    puts {PROCESSED_OUTPUT_BITSTREAM_COMPLETE}
    flush stdout
}
