`timescale 1ns/1ps
// Separate offline candidate. The already validated raw_camera_capture source
// remains unchanged. Only admission is gated; shared rst_n is never generated
// from lease expiry, host disconnect, frame budget or interlock stop.
module raw_camera_capture_guarded #(
    parameter WIDTH=640,HEIGHT=480,TIMEOUT_BITS=26,
    parameter [31:0] MAX_FRAMES=32'd3,MAX_LEASE_CYCLES=32'd3000000000
)(
    input core_clk,cam_clk,rst_n,
    input grant_valid,output wire grant_ready,input [31:0] grant_frames,grant_cycles,
    input stop_request,interlock_stop,
    input request_valid,output wire request_ready,
    input [27:0] request_base_address,
    input [31:0] request_frame_id,request_camera_id,input [1:0] request_eye,
    input vsync,href,input [7:0] data,
    output wire [27:0] awaddr,araddr,output wire [3:0] awlen,arlen,
    output wire awvalid,arvalid,input awready,arready,
    output wire [255:0] wdata,output wire [31:0] wstrb,input wready,wlast,
    input [255:0] rdata,input rvalid,rlast,input [3:0] rid,
    output wire byte_valid,input byte_ready,byte_done,output wire [7:0] byte_data,
    output wire bank_locked,capture_active,done,failed,output wire [7:0] fault,output wire [3:0] state,
    output wire [31:0] held_frame_id,held_camera_id,output wire [1:0] held_eye,
    output wire [31:0] source_crc,written_beats,output wire [15:0] frame_width,frame_height,
    output wire armed,in_flight,batch_done,grant_accepted,grant_rejected,requires_reset,draining,
    output wire [31:0] remaining_frames,remaining_cycles,admitted_frames,
    output wire [3:0] stop_reason
);
    wire core_request_valid,core_request_ready;
    raw_capture_lease #(.MAX_FRAMES(MAX_FRAMES),.MAX_LEASE_CYCLES(MAX_LEASE_CYCLES)) lease(
        .clk(core_clk),.rst_n(rst_n),.grant_valid(grant_valid),.grant_ready(grant_ready),
        .grant_frames(grant_frames),.grant_cycles(grant_cycles),.stop_request(stop_request),.interlock_stop(interlock_stop),
        .request_valid(request_valid),.request_ready(request_ready),.core_request_valid(core_request_valid),
        .core_request_ready(core_request_ready),.core_done(done),.core_failed(failed),.core_bank_locked(bank_locked),
        .armed(armed),.in_flight(in_flight),.batch_done(batch_done),.grant_accepted(grant_accepted),.grant_rejected(grant_rejected),
        .requires_reset(requires_reset),.draining(draining),.remaining_frames(remaining_frames),
        .remaining_cycles(remaining_cycles),.admitted_frames(admitted_frames),.stop_reason(stop_reason));
    raw_camera_capture #(.WIDTH(WIDTH),.HEIGHT(HEIGHT),.TIMEOUT_BITS(TIMEOUT_BITS)) raw(
        .core_clk(core_clk),.cam_clk(cam_clk),.rst_n(rst_n),.request_valid(core_request_valid),.request_ready(core_request_ready),
        .request_base_address(request_base_address),.request_frame_id(request_frame_id),.request_camera_id(request_camera_id),
        .request_eye(request_eye),.vsync(vsync),.href(href),.data(data),
        .awaddr(awaddr),.araddr(araddr),.awlen(awlen),.arlen(arlen),.awvalid(awvalid),.arvalid(arvalid),
        .awready(awready),.arready(arready),.wdata(wdata),.wstrb(wstrb),.wready(wready),.wlast(wlast),
        .rdata(rdata),.rvalid(rvalid),.rlast(rlast),.rid(rid),
        .byte_valid(byte_valid),.byte_ready(byte_ready),.byte_done(byte_done),.byte_data(byte_data),
        .bank_locked(bank_locked),.capture_active(capture_active),.done(done),.failed(failed),.fault(fault),.state(state),
        .held_frame_id(held_frame_id),.held_camera_id(held_camera_id),.held_eye(held_eye),
        .source_crc(source_crc),.written_beats(written_beats),.frame_width(frame_width),.frame_height(frame_height));
endmodule
