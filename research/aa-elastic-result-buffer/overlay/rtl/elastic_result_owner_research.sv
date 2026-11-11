`timescale 1ns/1ps
// Standalone CONTROL prototype. Not connected to canonical top, DDR or scan.
// ENABLE_ELASTIC_RESULT=0 means IDLE, NOT a legacy fallback.
// All addresses are 28-bit DDR UI words of 4 bytes. Default slots -> planes 2/3/4.
// RESULT2_BASE may instead select a disjoint in-span region; physical mapping is unverified.
// Reset is permitted only with coordinated quiescence of ALL external agents.
// Faults quarantine ownership; reset is not a demonstrated recovery protocol.
module elastic_result_owner_research #(
    parameter ENABLE_ELASTIC_RESULT=0,
    parameter [27:0] BANK_STRIDE=28'd33554432,
    parameter [27:0] FRAME_UNITS=28'd1036800,
    parameter [63:0] RESULT2_BASE=64'd4*BANK_STRIDE
)(
    input clk,rst_n,
    input external_fault,engine_failed,
    input source_valid,source_complete_qualified,source_bank,
    input [31:0] source_id,source_param_id,
    input source_correction,source_gamma,
    // Canonical 480-bit snapshot, MSB first: six 24-bit Brown fields,
    // seven 32-bit Brown fields, two 24-bit rotation centers, cos32, sin32.
    input [479:0] source_cfg,
    output source_ready,
    output [1:0] source_writable,
    output reg source_released,output reg released_bank,
    output reg [31:0] released_id,
    output engine_launch_valid,input engine_launch_ready,
    output reg engine_launch_source_bank,
    output reg [1:0] engine_launch_result_slot,
    output [27:0] engine_launch_source_base,engine_launch_result_base,
    output reg [31:0] engine_launch_id,engine_launch_param_id,
    output reg engine_launch_correction,engine_launch_gamma,
    output reg [479:0] engine_launch_cfg,
    input engine_done,engine_done_qualified,engine_read_quiescent,
    input engine_done_source_bank,
    input [1:0] engine_done_result_slot,
    input [27:0] engine_done_source_base,engine_done_result_base,
    input [31:0] engine_done_id,engine_done_crc,engine_done_param_id,
    input engine_done_correction,engine_done_gamma,engine_done_compressed,
    input [31:0] engine_done_rot_cos,engine_done_rot_sin,
    input display_request_valid,input [31:0] display_request_epoch,
    output display_request_ready,
    output display_grant_valid,input display_grant_ready,
    output reg [1:0] display_slot,
    output reg [27:0] display_base,
    output reg [31:0] display_id,display_crc,display_param_id,display_epoch,
    output reg [1:0] display_mode,
    output reg [31:0] display_rot_cos,display_rot_sin,
    output reg display_compressed,
    input display_done_valid,display_done_qualified,
    input display_reader_finished,display_reader_idle,display_scan_finished,display_fifo_empty,
    input [1:0] display_done_slot,
    input [31:0] display_done_id,display_done_crc,display_done_epoch,
    output reg processing,display_active,front_valid,
    output reg [1:0] front_slot,pending_count,
    output [2:0] free_result_mask,
    output reg result_published,
    output reg [31:0] completed_frames,
    output failed,output reg [7:0] fault
);
    // 64-bit arithmetic BEFORE narrowing, including the exclusive last word.
    localparam [63:0] ORIGINAL_END=64'd3*BANK_STRIDE+FRAME_UNITS;
    localparam [63:0] RESULT2_END=RESULT2_BASE+FRAME_UNITS;
    localparam RESULT2_DISJOINT=(RESULT2_BASE>=FRAME_UNITS) &&
        (RESULT2_END<=64'd1*BANK_STRIDE || RESULT2_BASE>=64'd1*BANK_STRIDE+FRAME_UNITS) &&
        (RESULT2_END<=64'd2*BANK_STRIDE || RESULT2_BASE>=64'd2*BANK_STRIDE+FRAME_UNITS) &&
        (RESULT2_END<=64'd3*BANK_STRIDE || RESULT2_BASE>=64'd3*BANK_STRIDE+FRAME_UNITS);
    localparam LAYOUT_OK=(BANK_STRIDE>=FRAME_UNITS) && BANK_STRIDE%128==0 &&
        FRAME_UNITS!=0 && ORIGINAL_END<=64'h10000000 && RESULT2_BASE<=64'h0fffffff &&
        RESULT2_END<=64'h10000000 && RESULT2_BASE%128==0 && RESULT2_DISJOINT;
    localparam ENABLED=(ENABLE_ELASTIC_RESULT==1);
    reg sticky_fault,launch_held,engine_started,grant_held;
    reg [1:0] queue_slot[0:2];
    reg [1:0] q_head,q_tail;
    reg [31:0] slot_id[0:2],slot_crc[0:2],slot_param[0:2];
    reg [1:0] slot_mode[0:2];
    reg [31:0] slot_cos[0:2],slot_sin[0:2];
    reg slot_compressed[0:2];
    reg [2:0] occupied;
    reg invariant_fault,free_found;
    reg [1:0] free_slot;
    integer i,j,idx;
    function [1:0] advance;
        input [1:0] n;
        begin advance=(n==2)?0:n+1'b1; end
    endfunction
    function [27:0] result_address;
        input [1:0] n;
        begin
            case(n)
                2'd0: result_address=64'd2*BANK_STRIDE;
                2'd1: result_address=64'd3*BANK_STRIDE;
                2'd2: result_address=RESULT2_BASE[27:0];
                default: result_address=28'd0;
            endcase
        end
    endfunction
    assign engine_launch_source_base=engine_launch_source_bank?BANK_STRIDE:28'd0;
    assign engine_launch_result_base=result_address(engine_launch_result_slot);
    wire expected_compressed=engine_launch_correction && !engine_launch_gamma &&
        engine_launch_cfg[63:32]==32'h40000000 && engine_launch_cfg[31:0]==0;
    // Completed CRC is an opaque token here. The real engine must independently
    // qualify counts/CRC/identity and read-side quiescence before this interface.
    wire raw_completion_ok=processing && engine_started && !launch_held &&
        engine_done_qualified && engine_read_quiescent &&
        engine_done_source_bank==engine_launch_source_bank &&
        engine_done_result_slot==engine_launch_result_slot &&
        engine_done_source_base==engine_launch_source_base &&
        engine_done_result_base==engine_launch_result_base &&
        engine_done_id==engine_launch_id && engine_done_param_id==engine_launch_param_id &&
        engine_done_correction==engine_launch_correction &&
        engine_done_gamma==engine_launch_gamma && !engine_done_gamma &&
        engine_done_rot_cos==engine_launch_cfg[63:32] && engine_done_rot_sin==engine_launch_cfg[31:0] &&
        engine_done_compressed==expected_compressed && pending_count<3;
    wire raw_display_done_ok=display_active && front_valid && !grant_held &&
        display_done_qualified && display_reader_finished && display_reader_idle &&
        display_scan_finished && display_fifo_empty && display_done_slot==front_slot &&
        display_done_id==display_id && display_done_crc==display_crc && display_done_epoch==display_epoch;
    // RFC1982-style half-range serial ordering: repeat grants also need a NEW
    // epoch. This rejects replay/backward request epochs, allows 32-bit wrap,
    // and requires caller advances by fewer than 2^31 refreshes per grant.
    wire [31:0] epoch_delta=display_request_epoch-display_epoch;
    wire request_epoch_ok=!front_valid || (epoch_delta!=0 && !epoch_delta[31]);
    // All pure pre-edge violations are collected before ANY publish/release/pop.
    // No combinational dependence on completion_ok or request/ready handshakes.
    wire early_owner_fault=!LAYOUT_OK || invariant_fault ||
        (source_valid && (!source_complete_qualified || source_gamma ||
            (processing && source_bank==engine_launch_source_bank))) ||
        (engine_done && !raw_completion_ok) ||
        (display_done_valid && !raw_display_done_ok) ||
        (display_request_valid && !request_epoch_ok);
    assign failed=ENABLED && (sticky_fault || external_fault || engine_failed);
    wire operate=ENABLED && rst_n && !failed && !early_owner_fault;
    wire completion_ok=operate && engine_done && raw_completion_ok;
    assign engine_launch_valid=operate && launch_held;
    assign display_grant_valid=operate && grant_held;
    assign source_ready=operate && !processing && !launch_held && free_found;
    assign source_writable=operate ?
        ~((processing?(engine_launch_source_bank?2'b10:2'b01):2'b00) |
          (source_valid?(source_bank?2'b10:2'b01):2'b00)):2'b00;
    assign free_result_mask=operate ? ~occupied:3'b000;
    assign display_request_ready=operate && !display_active && !grant_held &&
        (pending_count!=0 || front_valid || completion_ok);
    wire request_fire=display_request_valid && display_request_ready;
    wire pop_pending=request_fire && pending_count!=0;
    wire bypass_completion=request_fire && pending_count==0 && completion_ok;
    wire push_completion=completion_ok && !bypass_completion;
    always @* begin
        occupied=0;invariant_fault=0;free_found=0;free_slot=0;idx=0;
        if(q_head>2 || q_tail>2) invariant_fault=1;
        if(front_valid) begin
            if(front_slot>2) invariant_fault=1;
            else occupied[front_slot]=1;
        end
        if(display_active && (!front_valid || display_slot!=front_slot)) invariant_fault=1;
        if(grant_held && !display_active) invariant_fault=1;
        for(i=0;i<3;i=i+1) begin
            idx=q_head+i;
            if(idx>=3) idx=idx-3;
            if(i<pending_count) begin
                if(queue_slot[idx]>2) invariant_fault=1;
                else begin
                    if(occupied[queue_slot[idx]]) invariant_fault=1;
                    occupied[queue_slot[idx]]=1;
                end
            end
        end
        if(processing) begin
            if(engine_launch_result_slot>2) invariant_fault=1;
            else begin
                if(occupied[engine_launch_result_slot]) invariant_fault=1;
                occupied[engine_launch_result_slot]=1;
            end
        end
        if((launch_held || engine_started) && !processing) invariant_fault=1;
        for(j=0;j<3;j=j+1)
            if(!occupied[j] && !free_found) begin free_found=1;free_slot=j;end
    end
    integer k;
    reg [1:0] selected_slot;
    always @(posedge clk) begin
        if(!rst_n) begin
            sticky_fault<=0;fault<=0;processing<=0;launch_held<=0;engine_started<=0;
            display_active<=0;front_valid<=0;front_slot<=0;grant_held<=0;
            q_head<=0;q_tail<=0;pending_count<=0;source_released<=0;released_bank<=0;released_id<=0;
            result_published<=0;completed_frames<=0;
            engine_launch_source_bank<=0;engine_launch_result_slot<=0;engine_launch_id<=0;engine_launch_param_id<=0;
            engine_launch_correction<=0;engine_launch_gamma<=0;engine_launch_cfg<=0;
            display_slot<=0;display_base<=0;display_id<=0;display_crc<=0;display_param_id<=0;display_epoch<=0;
            display_mode<=0;display_rot_cos<=0;display_rot_sin<=0;display_compressed<=0;
            for(k=0;k<3;k=k+1) begin
                queue_slot[k]<=0;slot_id[k]<=0;slot_crc[k]<=0;slot_param[k]<=0;slot_mode[k]<=0;
                slot_cos[k]<=0;slot_sin[k]<=0;slot_compressed[k]<=0;
            end
        end else begin
            source_released<=0;result_published<=0;
            if(ENABLED && (external_fault || engine_failed || early_owner_fault)) begin
                sticky_fault<=1;
                if(!sticky_fault) fault<=external_fault?8'hE0:engine_failed?8'hE1:
                    !LAYOUT_OK?8'hE2:invariant_fault?8'hE3:
                    (display_done_valid && !raw_display_done_ok)?8'hE4:
                    (engine_done && !raw_completion_ok)?8'hE5:
                    (display_request_valid && !request_epoch_ok)?8'hE7:8'hE6;
            end
            // Fault branch preserves all ownership, queued descriptors and leases.
            if(operate) begin
                if(source_valid && source_ready) begin
                    processing<=1;launch_held<=1;engine_started<=0;
                    engine_launch_source_bank<=source_bank;engine_launch_result_slot<=free_slot;
                    engine_launch_id<=source_id;engine_launch_param_id<=source_param_id;
                    engine_launch_correction<=source_correction;engine_launch_gamma<=source_gamma;
                    engine_launch_cfg<=source_cfg;
                end
                if(engine_launch_valid && engine_launch_ready) begin launch_held<=0;engine_started<=1;end
                if(completion_ok) begin
                    processing<=0;engine_started<=0;
                    source_released<=1;released_bank<=engine_launch_source_bank;released_id<=engine_launch_id;
                    result_published<=1;completed_frames<=completed_frames+1'b1;
                    slot_id[engine_launch_result_slot]<=engine_done_id;slot_crc[engine_launch_result_slot]<=engine_done_crc;
                    slot_param[engine_launch_result_slot]<=engine_done_param_id;
                    slot_mode[engine_launch_result_slot]<={engine_done_gamma,engine_done_correction};
                    slot_cos[engine_launch_result_slot]<=engine_done_rot_cos;slot_sin[engine_launch_result_slot]<=engine_done_rot_sin;
                    slot_compressed[engine_launch_result_slot]<=engine_done_compressed;
                end
                if(push_completion) begin queue_slot[q_tail]<=engine_launch_result_slot;q_tail<=advance(q_tail);end
                if(pop_pending) q_head<=advance(q_head);
                case({push_completion,pop_pending})
                    2'b10: pending_count<=pending_count+1'b1;
                    2'b01: pending_count<=pending_count-1'b1;
                    default: pending_count<=pending_count;
                endcase
                if(request_fire) begin
                    display_active<=1;grant_held<=1;display_epoch<=display_request_epoch;
                    if(pop_pending) selected_slot=queue_slot[q_head];
                    else if(bypass_completion) selected_slot=engine_launch_result_slot;
                    else selected_slot=front_slot;
                    front_valid<=1;front_slot<=selected_slot;
                    display_slot<=selected_slot;display_base<=result_address(selected_slot);
                    if(bypass_completion) begin
                        display_id<=engine_done_id;display_crc<=engine_done_crc;display_param_id<=engine_done_param_id;
                        display_mode<={engine_done_gamma,engine_done_correction};
                        display_rot_cos<=engine_done_rot_cos;display_rot_sin<=engine_done_rot_sin;
                        display_compressed<=engine_done_compressed;
                    end else begin
                        display_id<=slot_id[selected_slot];display_crc<=slot_crc[selected_slot];display_param_id<=slot_param[selected_slot];
                        display_mode<=slot_mode[selected_slot];display_rot_cos<=slot_cos[selected_slot];display_rot_sin<=slot_sin[selected_slot];
                        display_compressed<=slot_compressed[selected_slot];
                    end
                end
                if(display_grant_valid && display_grant_ready) grant_held<=0;
                if(display_done_valid && raw_display_done_ok) display_active<=0;
            end
        end
    end
    initial begin
        if(ENABLE_ELASTIC_RESULT!=0 && ENABLE_ELASTIC_RESULT!=1) $fatal(1,"invalid elastic opt-in");
        if(ENABLED && !LAYOUT_OK) $fatal(1,"three-result layout exceeds 28-bit DDR UI range");
    end
endmodule
