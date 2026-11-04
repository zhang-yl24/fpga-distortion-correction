`timescale 1ns/1ps
// One startup observation epoch only; never a runtime recovery loop.
// Default requires48 good advances with every inter-advance gap below50ms.
module hdmi_observer_startup_guard #(
    parameter integer STABLE_GOOD_FRAMES=48,
    parameter integer MAX_GOOD_GAP_REF_CYCLES=1350000
)(
    input clk,rst_n,pipeline_released,ready,
    input [31:0] good_frames,bad_frames,
    output startup_armed,observer_epoch_reset
);
    reg warm_reset_started=0,warm_reset_done=0,ready_previous=0;
    reg [31:0] previous_good=0,previous_bad=0;
    reg [5:0] reset_count=0,clean_good_count=0;
    reg [20:0] good_gap=0;
    assign startup_armed=warm_reset_done;
    assign observer_epoch_reset=warm_reset_started && !warm_reset_done;
    always @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin
            warm_reset_started<=0;warm_reset_done<=0;ready_previous<=0;
            previous_good<=0;previous_bad<=0;reset_count<=0;
            clean_good_count<=0;good_gap<=0;
        end else if(!warm_reset_started && !pipeline_released)begin
            previous_good<=good_frames;previous_bad<=bad_frames;ready_previous<=ready;
            if(!ready || !ready_previous || bad_frames!=previous_bad)begin
                clean_good_count<=0;good_gap<=0;
            end else if(good_frames!=previous_good)begin
                // Reject backward/wrap/jumped snapshots, retaining exact query identity.
                if(good_frames>previous_good && good_frames-previous_good==32'd1)begin
                    good_gap<=0;
                    if(clean_good_count==0 || good_gap>=MAX_GOOD_GAP_REF_CYCLES-1)
                        clean_good_count<=1;
                    else if(clean_good_count==STABLE_GOOD_FRAMES-1)begin
                        clean_good_count<=STABLE_GOOD_FRAMES;
                        warm_reset_started<=1;reset_count<=0;
                    end else clean_good_count<=clean_good_count+1'b1;
                end else begin clean_good_count<=0;good_gap<=0;end
            end else if(clean_good_count!=0)begin
                if(good_gap>=MAX_GOOD_GAP_REF_CYCLES-1)begin
                    clean_good_count<=0;good_gap<=0;
                end else good_gap<=good_gap+1'b1;
            end
        end else if(warm_reset_started && !warm_reset_done)begin
            if(reset_count==6'd63)warm_reset_done<=1;
            else reset_count<=reset_count+1'b1;
        end
    end
endmodule
