# Raw upright diagnostic only; no bitstream or hardware.
set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/raw-camera-upright/d3/compiled/rtl/raw_camera_capture.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/raw-camera-upright/d3/compiled/rtl/experimental/capture_warmup.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/raw-camera-upright/d3/compiled/rtl/camera_preview.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/raw-camera-upright/d3/compiled/rtl/ddr_uart_frame.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/raw-camera-upright/d3/compiled/rtl/rgb565_burst_pack.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/raw-camera-upright/d3/compiled/rtl/video_async_fifo.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/raw-camera-upright/d3/compiled/rtl/camera_live_bridge.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/raw-camera-upright/d3/compiled/rtl/ddr_video_writer.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/raw-camera-upright/d3/compiled/rtl/dvp_rgb565_capture.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/raw-camera-upright/d3/compiled/rtl/reg16_i2c.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/raw-camera-upright/d3/compiled/rtl/uart_tx.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/raw-camera-upright/d3/compiled/rtl/video_pattern.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/raw-camera-upright/d3/compiled/rtl/experimental/ov5640_cadence_upright_init.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/raw-camera-upright/d3/compiled/rtl/experimental/raw_camera_power_ready.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/raw-camera-upright/d3/compiled/rtl/experimental/raw_camera_input_delay.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/raw-camera-upright/d3/compiled/platform/video_base/ipcore/ddr3_test/ddr3_test.idf}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/raw-camera-upright/d3/compiled/board/hdmi_tx_init.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/raw-camera-upright/d3/compiled/board/raw_camera_capture_cam2_delay.v}
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/raw-camera-upright/d3/compiled/board/bringup_pll.v}
add_constraint {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/raw-camera-upright/d3/compiled/board/raw-camera-upright-diagnostic.fdc}
compile -top_module raw_camera_capture_cam2_delay
synthesize -ads -selected_syn_tool_opt 2
dev_map
add_constraint {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/raw-camera-upright/d3/compiled/board/board1080-ddr-ioclk-priority.rcf}
pnr -optimize_multi_corner_timing -fix_hold_violation
if {[file exists {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/raw-camera-upright/d3/place_route/raw_camera_capture_cam2_delay_pnr.adf}]} {
    file copy {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/raw-camera-upright/d3/place_route/raw_camera_capture_cam2_delay_pnr.adf} {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/raw-camera-upright/d3/pre-sta-final.adf}
}
report_timing -force_to_run -delay_type min_max -max_path 1000 -nworst 4 -report_exception TRUE
