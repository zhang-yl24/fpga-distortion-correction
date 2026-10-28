`timescale 1ns/1ps
// Admission lease for finite raw-capture batches. Host silence cannot renew a
// lease: a fresh explicit grant is needed after the previous batch drains.
// Expiry/stop/interlock never resets a running DDR/UART transaction. A core
// fault remains quarantined until shared reset; bank ownership is not guessed.
// interlock_stop must be a synchronized decision from an independently
// validated temperature/safety source. This controller contains no ADC.
module raw_capture_lease #(
    parameter [31:0] MAX_FRAMES=32'd3,
    parameter [31:0] MAX_LEASE_CYCLES=32'd3000000000
)(
    input clk,rst_n,
    input grant_valid,output wire grant_ready,
    input [31:0] grant_frames,grant_cycles,
    input stop_request,interlock_stop,
    input request_valid,output wire request_ready,
    output wire core_request_valid,input core_request_ready,
    input core_done,core_failed,core_bank_locked,
    output reg armed,in_flight,batch_done,grant_accepted,grant_rejected,requires_reset,
    output wire draining,
    output reg [31:0] remaining_frames,remaining_cycles,admitted_frames,
    output reg [3:0] stop_reason
);
    localparam NONE=0,FRAME_BUDGET=1,LEASE_EXPIRED=2,OPERATOR_STOP=3,
        INTERLOCK=4,CORE_FAULT=5,INVALID_GRANT=6;
    reg session_started,completion_reported,grant_seen;
    wire live=rst_n && armed && remaining_cycles!=0 && remaining_frames!=0 &&
        !stop_request && !interlock_stop && !core_failed && !requires_reset;
    // A request is exposed to the core only on an immediately acceptable
    // cycle; no pending core VALID is withdrawn when a lease expires.
    assign request_ready=live && !in_flight && core_request_ready;
    assign core_request_valid=request_valid && request_ready;
    assign grant_ready=rst_n && !grant_seen && !armed && !in_flight && !core_bank_locked &&
        !requires_reset && !core_failed;
    assign draining=!armed && (in_flight || core_bank_locked) && !requires_reset;
    always @(posedge clk) begin
        if(!rst_n) begin
            armed<=0;in_flight<=0;batch_done<=0;grant_accepted<=0;grant_rejected<=0;requires_reset<=0;
            remaining_frames<=0;remaining_cycles<=0;admitted_frames<=0;stop_reason<=NONE;
            session_started<=0;completion_reported<=0;grant_seen<=0;
        end else begin
            batch_done<=0;grant_accepted<=0;grant_rejected<=0;
            // A held/stale grant level cannot restart a later batch. The
            // command source must present a low cycle before a fresh grant.
            if(!grant_valid) grant_seen<=0;
            if(armed && remaining_cycles!=0) remaining_cycles<=remaining_cycles-1'b1;
            if(core_done) in_flight<=0;
            // Every fresh pulse receives one explicit result, even if a
            // readiness/interlock transition races the command producer.
            if(grant_valid && !grant_seen) begin
                grant_seen<=1;
                if(!grant_ready || grant_frames==0 || grant_frames>MAX_FRAMES || grant_cycles==0 ||
                   grant_cycles>MAX_LEASE_CYCLES || stop_request || interlock_stop) begin
                    grant_rejected<=1;stop_reason<=interlock_stop ? INTERLOCK:INVALID_GRANT;
                end else begin
                    grant_accepted<=1;armed<=1;remaining_frames<=grant_frames;remaining_cycles<=grant_cycles;
                    admitted_frames<=0;stop_reason<=NONE;session_started<=1;completion_reported<=0;
                end
            end
            if(core_request_valid && core_request_ready) begin
                in_flight<=1;admitted_frames<=admitted_frames+1'b1;
                remaining_frames<=remaining_frames-1'b1;
                if(remaining_frames==1) begin armed<=0;stop_reason<=FRAME_BUDGET;end
            end
            if(armed && remaining_cycles==1) begin armed<=0;stop_reason<=LEASE_EXPIRED;end
            if(stop_request || interlock_stop) begin
                armed<=0;
                if(armed) stop_reason<=interlock_stop ? INTERLOCK:OPERATOR_STOP;
            end
            if(core_failed) begin armed<=0;requires_reset<=1;stop_reason<=CORE_FAULT;end
            if(session_started && !armed && !in_flight && !core_bank_locked &&
               !core_failed && !requires_reset && !completion_reported && !(grant_valid && grant_ready)) begin
                batch_done<=1;completion_reported<=1;
            end
        end
    end
endmodule
