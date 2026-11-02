`timescale 1ns/1ps
// Portable retained-source 720p register/live-digital frontend.
// VS/HREF inputs are logical active-high. The board caller binds inversions
// and packs RGB565 low byte first; this observer never stores pixel payloads.
// raw_authorize gates NEW requests only: it must never reset accepted DDR/UART
// transactions. The retained monitor's CDC requires separate physical signoff.
module ov5640_current720_frontend #(
    parameter INIT_RESET_CYCLES=270000,INIT_WAIT_CYCLES=1350000,MS_CYCLES=27000,
    I2C_QUARTER_CYCLES=68,I2C_TIMEOUT_CYCLES=1350000,
    ACTIVITY_WINDOW_REF_CYCLES=27000,SNAPSHOT_INTERVAL_REF_CYCLES=27000,
    STARTUP_REF_CYCLES=27000000,MAX_PCLK_IDLE_REF_CYCLES=270000,
    MAX_FRAME_IDLE_REF_CYCLES=2700000,MAX_SNAPSHOT_IDLE_REF_CYCLES=270000
)(input ref_clk,pclk,rst_n,vsync_active,href_active,
    inout cam_rst_n,cam_scl,cam_sda,
    output configured,raw_authorize,failed,
    output [7:0] fault,init_error,monitor_fault,
    output [15:0] sensor_id,failed_address,
    output [31:0] good_frames,bad_frames,pclk_edges_per_window,
    output [15:0] last_frame_lines,last_line_bytes,
    output pclk_fresh,vsync_fresh,href_fresh,frame_fresh,snapshot_fresh,
    output [7:0] observed_value,expected_value,output observed_valid,
    output [3:0] last_bus_error,
    output [9:0] action_index,failed_action,writes_completed,verified_write_noacks,
    output final_wake_verified);
    wire init_failed,monitor_failed,monitor_authorize;
    ov5640_current720_init #(.RESET_CYCLES(INIT_RESET_CYCLES),
        .WAIT_CYCLES(INIT_WAIT_CYCLES),.MS_CYCLES(MS_CYCLES),
        .I2C_QUARTER_CYCLES(I2C_QUARTER_CYCLES),.I2C_TIMEOUT_CYCLES(I2C_TIMEOUT_CYCLES)) initializer(
        .clk(ref_clk),.rst_n(rst_n),.cam_rst_n(cam_rst_n),.cam_scl(cam_scl),.cam_sda(cam_sda),
        .sensor_id(sensor_id),.configured(configured),.failed(init_failed),
        .error_code(init_error),.failed_address(failed_address),
        .observed_value(observed_value),.expected_value(expected_value),.observed_valid(observed_valid),
        .last_bus_error(last_bus_error),.action_index(action_index),.failed_action(failed_action),
        .writes_completed(writes_completed),.verified_write_noacks(verified_write_noacks),
        .final_wake_verified(final_wake_verified));
    dvp_mode_admission_monitor #(.BYTES_PER_LINE(2560),.LINES_PER_FRAME(720),
        .ACTIVITY_WINDOW_REF_CYCLES(ACTIVITY_WINDOW_REF_CYCLES),
        .SNAPSHOT_INTERVAL_REF_CYCLES(SNAPSHOT_INTERVAL_REF_CYCLES),
        .STARTUP_REF_CYCLES(STARTUP_REF_CYCLES),.MAX_PCLK_IDLE_REF_CYCLES(MAX_PCLK_IDLE_REF_CYCLES),
        .MAX_VSYNC_IDLE_REF_CYCLES(MAX_FRAME_IDLE_REF_CYCLES),
        .MAX_HREF_IDLE_REF_CYCLES(MAX_FRAME_IDLE_REF_CYCLES),
        .MAX_FRAME_IDLE_REF_CYCLES(MAX_FRAME_IDLE_REF_CYCLES),
        .MAX_SNAPSHOT_IDLE_REF_CYCLES(MAX_SNAPSHOT_IDLE_REF_CYCLES)) monitor(
        .ref_clk(ref_clk),.pclk(pclk),.rst_n(rst_n),.enable(configured && !init_failed),
        .vsync_active(vsync_active),.href_active(href_active),.raw_authorize(monitor_authorize),
        .failed(monitor_failed),.fault(monitor_fault),.good_frames(good_frames),.bad_frames(bad_frames),
        .pclk_edges_per_window(pclk_edges_per_window),.last_frame_lines(last_frame_lines),
        .last_line_bytes(last_line_bytes),.pclk_fresh(pclk_fresh),.vsync_fresh(vsync_fresh),
        .href_fresh(href_fresh),.frame_fresh(frame_fresh),.snapshot_fresh(snapshot_fresh));
    // good_frames is a coherent ref_clk-domain held snapshot. A single good
    // frame is insufficient even when the unchanged monitor grants admission.
    assign raw_authorize=configured && !init_failed && monitor_authorize &&
        !monitor_failed && good_frames>=32'd2;
    assign failed=init_failed || monitor_failed;
    assign fault=init_failed ? init_error:monitor_fault;
endmodule
