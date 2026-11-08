`timescale 1ns/1ps
// Passive only. Existing safe ref-domain snapshots are not control inputs here.
// The one new pixel-domain signal is the geometry reset-release FF level,
// synchronized before use. It is evidence of that FF, not every reset load.
module hdmi_observer_epoch_history(
    input ref_clk,global_reset_n,observer_epoch_reset,
    input source_domain_reset_n,source_fault_valid_ref,ref_fault_valid,snapshot_seen_ref,
    input [31:0] good_frames,bad_frames,
    output [7:0] history_flags,
    output reg [7:0] pulse_count=0,
    output reg [31:0] pulse_start_tick=0,pulse_end_tick=0,
    output reg [31:0] first_bad_tick=0,first_bad_value=0,
    output reg [31:0] first_snapshot_tick=0,first_snapshot_good=0,first_snapshot_bad=0
);
    (* PAP_ASYNC_REG=1,async_reg="true" *) reg [1:0] pixel_reset_sync=0;
    reg [31:0] uptime=0;
    reg previous_pulse=0,first_snapshot_seen=0;
    // Qualify new history only after snapshot_seen was low at the end of this pulse.
    reg snapshot_reset_clear=0;
    reg [6:0] pulse_width=0;
    reg saw_ref_zero=0,saw_pixel_reset=0,first_bad_seen=0,pulse_finished=0;
    reg width64=0,width_error=0,uptime_wrap=0;
    assign history_flags={first_snapshot_seen,uptime_wrap,width_error,width64,
                          pulse_finished,first_bad_seen,saw_pixel_reset,saw_ref_zero};
    always @(posedge ref_clk or negedge global_reset_n)begin
        if(!global_reset_n)begin
            pixel_reset_sync<=0;uptime<=0;previous_pulse<=0;pulse_width<=0;snapshot_reset_clear<=0;
            pulse_count<=0;pulse_start_tick<=0;pulse_end_tick<=0;
            first_bad_tick<=0;first_bad_value<=0;
            first_snapshot_seen<=0;first_snapshot_tick<=0;first_snapshot_good<=0;first_snapshot_bad<=0;
            saw_ref_zero<=0;saw_pixel_reset<=0;first_bad_seen<=0;pulse_finished<=0;
            width64<=0;width_error<=0;uptime_wrap<=0;
        end else begin
            pixel_reset_sync<={pixel_reset_sync[0],source_domain_reset_n};
            uptime<=uptime+1'b1;if(uptime==32'hffffffff)uptime_wrap<=1;
            previous_pulse<=observer_epoch_reset;
            if(observer_epoch_reset && !previous_pulse)begin
                if(pulse_count!=8'hff)pulse_count<=pulse_count+1'b1;
                pulse_start_tick<=uptime;pulse_width<=1;
                saw_ref_zero<=0;saw_pixel_reset<=0;first_bad_seen<=0;pulse_finished<=0;
                width64<=0;width_error<=0;first_bad_tick<=0;first_bad_value<=0;first_snapshot_seen<=0;
            end else if(observer_epoch_reset && pulse_width!=7'h7f)pulse_width<=pulse_width+1'b1;
            if(observer_epoch_reset)begin
                snapshot_reset_clear<=!snapshot_seen_ref;
                if(good_frames==0 && bad_frames==0 && !source_fault_valid_ref && !ref_fault_valid)saw_ref_zero<=1;
                if(!pixel_reset_sync[1])saw_pixel_reset<=1;
            end
            if(!observer_epoch_reset && previous_pulse)begin
                pulse_end_tick<=uptime;pulse_finished<=1;
                width64<=pulse_width==7'd64;width_error<=pulse_width!=7'd64;
            end
            if(pulse_finished && !observer_epoch_reset && !first_snapshot_seen && snapshot_reset_clear && snapshot_seen_ref)begin
                first_snapshot_seen<=1;first_snapshot_tick<=uptime;
                first_snapshot_good<=good_frames;first_snapshot_bad<=bad_frames;
            end
            if(pulse_finished && !observer_epoch_reset && !first_bad_seen &&
               snapshot_reset_clear && snapshot_seen_ref &&
               (source_fault_valid_ref || bad_frames!=0))begin
                first_bad_seen<=1;first_bad_tick<=uptime;first_bad_value<=bad_frames;
            end
        end
    end
endmodule
