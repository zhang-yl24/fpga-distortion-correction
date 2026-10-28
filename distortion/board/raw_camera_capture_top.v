`timescale 1ns/1ps
// OFFLINE INTEGRATION CANDIDATE, not a pin-verified new-camera board image.
// core_clk/DDR interface are provided by the existing validated platform.
// Sensor identity is read at runtime before writes by ov5640_init. New-module
// voltage, pinout, PCLK/HS/VS polarity, byte order and pad mask require real
// verification. No FDC or programming recipe is supplied by this candidate.
// CAMERA_ID/EYE are user-assigned metadata tags, not silicon serial numbers.
module raw_camera_capture_top #(
    parameter CAMERA_ID=0,EYE=0,CAMERA_PAD_MASK=16'h7ff0,
    parameter INVERT_VSYNC=1,INVERT_HREF=1,UART_BAUD=921600
)(
    input clk_27m,core_clk,cam_pclk,rst_n,ddr_ready,
    input request_valid,output wire request_ready,input [31:0] request_frame_id,
    input [27:0] request_base_address,
    input cam_vsync,cam_href,input [7:0] cam_data,
    inout cam_rst_n,cam_scl,cam_sda,
    output wire uart_txd,
    output wire [15:0] sensor_id,output wire sensor_ready,sensor_failed,
    output wire [7:0] sensor_error,output wire [15:0] sensor_failed_address,
    output wire [27:0] awaddr,araddr,output wire [3:0] awlen,arlen,
    output wire awvalid,arvalid,input awready,arready,
    output wire [255:0] wdata,output wire [31:0] wstrb,input wready,wlast,
    input [255:0] rdata,input rvalid,rlast,input [3:0] rid,
    output wire done,failed,output wire [7:0] fault,output wire [3:0] state,
    output wire bank_locked,output wire [31:0] held_frame_id,held_camera_id,
    output wire [1:0] held_eye,output wire [31:0] source_crc,written_beats
);
    // Reference VGA RGB565 initialization only; this is not a claim that the
    // newly arrived camera has been identified or accepts these settings.
    ov5640_init #(.DYNAMIC_PAD_MASK(1)) sensor(
        .clk(clk_27m),.rst_n(rst_n),.cam_rst_n(cam_rst_n),.cam_scl(cam_scl),.cam_sda(cam_sda),
        .trial_pad_mask(CAMERA_PAD_MASK),.sensor_id(sensor_id),.ready(sensor_ready),
        .failed(sensor_failed),.error_code(sensor_error),.failed_address(sensor_failed_address),
        .commands_written(),.verified_write_noacks(),.observed_value(),.expected_value());
    (* async_reg="true" *) reg [1:0] sensor_ready_sync=0;
    always @(posedge core_clk or negedge rst_n)
        if(!rst_n) sensor_ready_sync<=0;
        else sensor_ready_sync<={sensor_ready_sync[0],sensor_ready && !sensor_failed};
    wire core_request_ready;
    assign request_ready=core_request_ready && sensor_ready_sync[1] && ddr_ready;
    wire byte_valid,byte_ready,byte_done,serial_busy;wire [7:0] byte_data;
    raw_camera_capture capture(
        .core_clk(core_clk),.cam_clk(cam_pclk),.rst_n(rst_n),
        .request_valid(request_valid && sensor_ready_sync[1] && ddr_ready),.request_ready(core_request_ready),
        .request_base_address(request_base_address),.request_frame_id(request_frame_id),
        .request_camera_id(CAMERA_ID),.request_eye(EYE[1:0]),
        .vsync(INVERT_VSYNC ? !cam_vsync:cam_vsync),.href(INVERT_HREF ? !cam_href:cam_href),.data(cam_data),
        .awaddr(awaddr),.araddr(araddr),.awlen(awlen),.arlen(arlen),.awvalid(awvalid),.arvalid(arvalid),
        .awready(awready),.arready(arready),.wdata(wdata),.wstrb(wstrb),.wready(wready),.wlast(wlast),
        .rdata(rdata),.rvalid(rvalid),.rlast(rlast),.rid(rid),
        .byte_valid(byte_valid),.byte_ready(byte_ready),.byte_done(byte_done),.byte_data(byte_data),
        .bank_locked(bank_locked),.capture_active(),.done(done),.failed(failed),.fault(fault),.state(state),
        .held_frame_id(held_frame_id),.held_camera_id(held_camera_id),.held_eye(held_eye),
        .source_crc(source_crc),.written_beats(written_beats),.frame_width(),.frame_height());
    uart_tx #(.CLOCK_HZ(125000000),.BAUD(UART_BAUD)) serial(
        .clk(core_clk),.rst_n(rst_n),.start(byte_valid && byte_ready),.data(byte_data),
        .tx(uart_txd),.busy(serial_busy),.done(byte_done));
    assign byte_ready=!serial_busy;
endmodule
