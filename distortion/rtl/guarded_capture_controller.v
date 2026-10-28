`timescale 1ns/1ps
// Core-clock command/admission/status integration. Boot is disarmed. Camera
// initialization and HDMI sink state never create grants. Stop/temperature
// failure removes admission only; an accepted DDR/UART transaction drains.
module guarded_capture_controller #(
    parameter WIDTH=640,HEIGHT=480,TIMEOUT_BITS=26,CORE_CLOCK_HZ=125000000,
    parameter [31:0] STATUS_PERIOD_CYCLES=125000000,BUILD_TAG=32'h52473201,
    parameter [31:0] SAFETY_MAX_AGE=125000000,TEMP_MAX_AGE=54000000,
    parameter [31:0] CAMERA_ID=32'h43414d32,parameter [1:0] CAMERA_SLOT=2'b10
)(
    input core_clk,cam_clk,rst_n,
    input camera_ready,ddr_ready,warmup_ready,safety_ok,safety_snapshot_valid,
    input [31:0] safety_snapshot_age,
    input temp_valid,temp_failed,temp_over,input [7:0] temp_fault,
    input [4:0] temp_alarm,input [15:0] temp_raw,input [11:0] temp_code,
    input [31:0] temp_age,temp_samples,temp_conversions,input [95:0] camera_info,
    input rx_valid,input [7:0] rx_data,input rx_framing_error,
    input vsync,href,input [7:0] data,
    output wire [27:0] awaddr,araddr,output wire [3:0] awlen,arlen,
    output wire awvalid,arvalid,input awready,arready,
    output wire [255:0] wdata,output wire [31:0] wstrb,input wready,wlast,
    input [255:0] rdata,input rvalid,rlast,input [3:0] rid,
    output wire byte_valid,input byte_ready,byte_done,output wire [7:0] byte_data,
    output wire armed,in_flight,bank_locked,raw_done,raw_failed,requires_reset,
    output wire [7:0] raw_fault,output wire [3:0] raw_state,stop_reason,
    output wire [31:0] admitted_frames,completed_frames,remaining_frames,remaining_cycles,
    output wire capture_active,core_idle,ready_for_grant,status_active,status_pending,
    output wire raw_uart_locked,command_busy,reply_event,
    output wire [31:0] frame_sequence,output wire grant_accepted,grant_rejected
);
    wire grant_valid,grant_ready,stop_pulse,batch_done,draining,request_ready;
    wire [31:0] grant_frames,grant_cycles,session_id,accepted_count,rejected_count,
        duplicate_count,rx_error_count,held_frame_id,held_camera_id,source_crc,written_beats;
    wire [15:0] last_received_seq,last_accepted_seq,requested_frames,lease_ms;
    wire [7:0] last_opcode,last_result;wire [1:0] held_eye;
    wire [15:0] sensor_id,camera_failed_address;wire [7:0] camera_error,camera_observed,camera_expected;
    wire [8:0] camera_writes,camera_noacks;wire info_camera_ready,camera_failed,hd_ready,pll_lock;
    wire [3:0] hd_error;wire [13:0] unused_info;
    reg [31:0] sequence_counter=0,completion_count=0,uptime_ms=0;
    reg [16:0] ms_divider=0;reg fault_seen=0,safety_previous=0;
    wire raw_valid,raw_ready,raw_byte_done,status_valid,status_ready,status_byte_done,admission_allowed;
    wire [7:0] raw_data,status_data;
    wire request_valid=armed && camera_ready && ddr_ready && warmup_ready && safety_ok && admission_allowed;
    wire request_accepted=request_valid && request_ready;
    assign frame_sequence=sequence_counter;
    assign completed_frames=completion_count;
    assign core_idle=!armed && !in_flight && !bank_locked && !raw_uart_locked;
    assign ready_for_grant=core_idle && !raw_failed && !requires_reset && camera_ready &&
        info_camera_ready && !camera_failed && sensor_id==16'h5640 && ddr_ready && warmup_ready && safety_ok;
    always @(posedge core_clk)begin
        if(!rst_n)begin sequence_counter<=0;completion_count<=0;ms_divider<=0;uptime_ms<=0;fault_seen<=0;safety_previous<=0;end
        else begin
            fault_seen<=raw_failed;safety_previous<=safety_ok;
            if(request_accepted)sequence_counter<=sequence_counter+1'b1;
            // Completed frames are boot-global; admitted_frames remains the
            // lease's per-grant counter. A new grant must not erase evidence.
            if(raw_done)completion_count<=completion_count+1'b1;
            if(ms_divider==CORE_CLOCK_HZ/1000-1)begin ms_divider<=0;uptime_ms<=uptime_ms+1'b1;end
            else ms_divider<=ms_divider+1'b1;
        end
    end
    guarded_command_engine #(.CLOCK_HZ(CORE_CLOCK_HZ)) commands(.clk(core_clk),.rst_n(rst_n),
        .byte_valid(rx_valid),.byte_data(rx_data),.framing_error(rx_framing_error),
        .core_idle(core_idle),.fault_active(raw_failed || requires_reset),.can_grant(ready_for_grant),
        .grant_ready(grant_ready),.grant_accepted(grant_accepted),.grant_rejected(grant_rejected),
        .grant_valid(grant_valid),.grant_frames(grant_frames),.grant_cycles(grant_cycles),
        .stop_pulse(stop_pulse),.reply_event(reply_event),.command_busy(command_busy),
        .session_id(session_id),.last_received_seq(last_received_seq),.last_accepted_seq(last_accepted_seq),
        .last_opcode(last_opcode),.last_result(last_result),.accepted_count(accepted_count),
        .rejected_count(rejected_count),.duplicate_count(duplicate_count),.rx_error_count(rx_error_count),
        .requested_frames(requested_frames),.lease_ms(lease_ms));
    raw_camera_capture_guarded #(.WIDTH(WIDTH),.HEIGHT(HEIGHT),.TIMEOUT_BITS(TIMEOUT_BITS),
        .MAX_FRAMES(3),.MAX_LEASE_CYCLES(32'd3000000000)) pipeline(.core_clk(core_clk),.cam_clk(cam_clk),.rst_n(rst_n),
        .grant_valid(grant_valid),.grant_ready(grant_ready),.grant_frames(grant_frames),.grant_cycles(grant_cycles),
        .stop_request(stop_pulse),.interlock_stop(!safety_ok),.request_valid(request_valid),.request_ready(request_ready),
        .request_base_address(28'b0),.request_frame_id(sequence_counter+1'b1),.request_camera_id(CAMERA_ID),.request_eye(CAMERA_SLOT),
        .vsync(vsync),.href(href),.data(data),.awaddr(awaddr),.araddr(araddr),.awlen(awlen),.arlen(arlen),
        .awvalid(awvalid),.arvalid(arvalid),.awready(awready),.arready(arready),.wdata(wdata),.wstrb(wstrb),
        .wready(wready),.wlast(wlast),.rdata(rdata),.rvalid(rvalid),.rlast(rlast),.rid(rid),
        .byte_valid(raw_valid),.byte_ready(raw_ready),.byte_done(raw_byte_done),.byte_data(raw_data),
        .bank_locked(bank_locked),.capture_active(capture_active),.done(raw_done),.failed(raw_failed),
        .fault(raw_fault),.state(raw_state),.held_frame_id(held_frame_id),.held_camera_id(held_camera_id),.held_eye(held_eye),
        .source_crc(source_crc),.written_beats(written_beats),.frame_width(),.frame_height(),
        .armed(armed),.in_flight(in_flight),.batch_done(batch_done),.grant_accepted(grant_accepted),
        .grant_rejected(grant_rejected),.requires_reset(requires_reset),.draining(draining),
        .remaining_frames(remaining_frames),.remaining_cycles(remaining_cycles),.admitted_frames(admitted_frames),.stop_reason(stop_reason));
    assign {unused_info,info_camera_ready,camera_failed,hd_ready,hd_error,pll_lock,camera_expected,
        camera_observed,camera_noacks,camera_writes,camera_failed_address,camera_error,sensor_id}=camera_info;
    wire temp_stale=!safety_snapshot_valid || safety_snapshot_age>=SAFETY_MAX_AGE || temp_age>=TEMP_MAX_AGE;
    wire [15:0] flags={core_idle,camera_failed,temp_stale,temp_over,temp_failed,temp_valid,draining,
        requires_reset,raw_failed,bank_locked,in_flight,armed,safety_ok,warmup_ready,ddr_ready,camera_ready};
    wire [31:0] status_sequence;
    reg [991:0] payload;
    always @* begin
        payload=0;
        payload[0*8+:64]=64'h3230544154534750;payload[8*8+:16]=128;
        payload[10*8+:16]=2;payload[12*8+:32]=BUILD_TAG;
        payload[16*8+:32]=uptime_ms;payload[20*8+:32]=session_id;
        payload[24*8+:16]=last_received_seq;payload[26*8+:16]=last_accepted_seq;
        payload[28*8+:8]=last_opcode;payload[29*8+:8]=last_result;payload[30*8+:16]=flags;
        payload[32*8+:32]=accepted_count;payload[36*8+:32]=rejected_count;
        payload[40*8+:32]=duplicate_count;payload[44*8+:32]=rx_error_count;
        payload[48*8+:32]=admitted_frames;payload[52*8+:32]=completed_frames;
        payload[56*8+:32]=remaining_frames;payload[60*8+:32]=remaining_cycles;
        payload[64*8+:32]=held_frame_id;payload[68*8+:32]=source_crc;payload[72*8+:32]=written_beats;
        payload[76*8+:16]=temp_raw;payload[78*8+:16]={4'b0,temp_code};
        payload[80*8+:32]=temp_age;payload[84*8+:32]=temp_samples;payload[88*8+:32]=temp_conversions;
        payload[92*8+:16]=sensor_id;payload[94*8+:8]=camera_error;payload[95*8+:8]=raw_fault;
        payload[96*8+:16]=camera_failed_address;payload[98*8+:8]=camera_observed;payload[99*8+:8]=camera_expected;
        payload[100*8+:16]={7'b0,camera_writes};payload[102*8+:16]={7'b0,camera_noacks};
        payload[104*8+:8]={4'b0,stop_reason};payload[105*8+:8]={4'b0,raw_state};
        payload[106*8+:8]=temp_fault;payload[107*8+:8]={3'b0,temp_alarm};
        payload[108*8+:32]=status_sequence+1'b1;payload[112*8+:32]=safety_snapshot_age;
        payload[116*8+:16]=requested_frames;payload[118*8+:16]=lease_ms;
    end
    guarded_status_uart #(.PERIOD_CYCLES(STATUS_PERIOD_CYCLES)) status(.clk(core_clk),.rst_n(rst_n),
        .request(reply_event || raw_done || batch_done || (raw_failed && !fault_seen) || safety_previous!=safety_ok),.raw_locked(raw_uart_locked),
        .defer_snapshot(command_busy),.payload(payload),.pending(status_pending),.active(status_active),
        .record_started(),.record_done(),.record_sequence(status_sequence),.byte_valid(status_valid),
        .byte_ready(status_ready),.byte_done(status_byte_done),.byte_data(status_data));
    guarded_uart_arbiter arbiter(.clk(core_clk),.rst_n(rst_n),.raw_admitted(request_accepted),
        .raw_done(raw_done),.raw_failed(raw_failed),.raw_valid(raw_valid),.raw_data(raw_data),
        .raw_ready(raw_ready),.raw_byte_done(raw_byte_done),.status_valid(status_valid),.status_data(status_data),
        .status_ready(status_ready),.status_byte_done(status_byte_done),.status_pending(status_pending),
        .status_active(status_active),.command_busy(command_busy),.reply_event(reply_event),
        .raw_locked(raw_uart_locked),.admission_allowed(admission_allowed),.tx_valid(byte_valid),
        .tx_data(byte_data),.tx_ready(byte_ready),.tx_done(byte_done));
endmodule
