`timescale 1ns/1ps
// One raw RGB565 acquisition -> frozen DDR bank -> PGFRAME1 UART bytes.
// No lens model, coordinate map, Gamma, rotation or corrected-image bank.
// request_* metadata is latched at admission and held through the final UART
// stop-bit acknowledgement. Camera/eye identity is status metadata; PGFRAME1
// carries the native frame_id/size/CRC, not a claim of stereo synchronization.
// The caller exclusively owns the single source bank while bank_locked=1.
// Faults require a shared reset; never reset one CDC FIFO domain on its own.
module raw_camera_capture #(
    parameter WIDTH=640, HEIGHT=480, TIMEOUT_BITS=26
)(
    input core_clk,cam_clk,rst_n,
    input request_valid,output wire request_ready,
    input [27:0] request_base_address,
    input [31:0] request_frame_id,request_camera_id,input [1:0] request_eye,
    input vsync,href,input [7:0] data,
    output wire [27:0] awaddr,araddr,output wire [3:0] awlen,arlen,
    output wire awvalid,arvalid,input awready,arready,
    output wire [255:0] wdata,output wire [31:0] wstrb,input wready,wlast,
    input [255:0] rdata,input rvalid,rlast,input [3:0] rid,
    output wire byte_valid,input byte_ready,byte_done,output wire [7:0] byte_data,
    output wire bank_locked,output wire capture_active,
    output reg done,failed,output reg [7:0] fault,
    output reg [3:0] state,
    output reg [31:0] held_frame_id,held_camera_id,output reg [1:0] held_eye,
    output wire [31:0] source_crc,written_beats,
    output wire [15:0] frame_width,frame_height
);
    localparam IDLE=0,RESET_TRANSACTION=1,CAPTURE=2,START_EXPORT=3,
        EXPORT=4,COMPLETE=5,FAULT=6;
    localparam FRAME_BEATS=WIDTH*HEIGHT/16;
    localparam FRAME_UNITS=WIDTH*HEIGHT/2; // DDR address unit = four bytes.
    localparam VALID_SIZE=WIDTH>=16 && WIDTH<=4095 && HEIGHT>=1 && HEIGHT<=4095 &&
        WIDTH%16==0 && WIDTH*HEIGHT%256==0;
    (* async_reg="true" *) reg [1:0] reset_sync=0;
    always @(posedge core_clk or negedge rst_n)
        if(!rst_n) reset_sync<=0;else reset_sync<={reset_sync[0],1'b1};
    wire local_rst_n=reset_sync[1];
    reg transaction_active;
    reg [4:0] reset_wait;
    reg [27:0] held_base;
    wire [28:0] requested_end={1'b0,request_base_address}+FRAME_UNITS;
    wire valid_layout=VALID_SIZE && request_base_address[6:0]==0 &&
        requested_end<=29'h10000000;
    assign frame_width=WIDTH;assign frame_height=HEIGHT;
    assign request_ready=local_rst_n && !failed && (state==IDLE || state==COMPLETE);
    assign bank_locked=state==RESET_TRANSACTION || (transaction_active && state!=COMPLETE);
    assign capture_active=state==CAPTURE;
    // Keep the producer frozen and metadata stable through COMPLETE/FAULT.
    // Only a new admitted transaction or shared reset clears the bridge.
    wire transaction_rst_n=local_rst_n && transaction_active;
    wire [9:0] fifo_available;
    wire fifo_ready,fifo_valid,fifo_pop,source_done,source_valid;
    wire [257:0] fifo_data;
    camera_live_bridge #(.WIDTH(WIDTH),.HEIGHT(HEIGHT)) bridge(
        .cam_clk(cam_clk),.ddr_clk(core_clk),.rst_n(transaction_rst_n),.arm(transaction_active),
        .vsync(vsync),.href(href),.data(data),
        .fifo_rd_en(fifo_pop),.fifo_data(fifo_data),.fifo_valid(fifo_valid),.fifo_ready(fifo_ready),
        .fifo_available(fifo_available),.source_done(source_done),.source_valid(source_valid),
        .source_checksum(source_crc));
    wire writer_done,writer_failed;wire [7:0] writer_fault;
    wire [31:0] write_checksum;
    ddr_video_writer #(.FRAME_BEATS(FRAME_BEATS),.TIMEOUT_BITS(TIMEOUT_BITS)) writer(
        .clk(core_clk),.rst_n(transaction_rst_n),.base_address(held_base),
        .fifo_available(fifo_available),.fifo_ready(fifo_ready),.fifo_rd_en(fifo_pop),
        .fifo_valid(fifo_valid),.fifo_data(fifo_data),.source_done(source_done),
        .source_valid(source_valid),.source_checksum(source_crc),
        .awaddr(awaddr),.awlen(awlen),.awvalid(awvalid),.awready(awready),
        .wdata(wdata),.wstrb(wstrb),.wready(wready),.wlast(wlast),
        .state(),.done(writer_done),.failed(writer_failed),.fault(writer_fault),
        .written_beats(written_beats),.write_checksum(write_checksum));
    wire exporter_idle,exporter_done,exporter_failed;wire [7:0] exporter_fault;
    ddr_uart_frame #(.WIDTH(WIDTH),.HEIGHT(HEIGHT),.TIMEOUT_BITS(TIMEOUT_BITS)) exporter(
        .clk(core_clk),.rst_n(transaction_rst_n),.start(state==START_EXPORT),
        .base_address(held_base),.frame_id(held_frame_id),.source_crc(source_crc),
        .araddr(araddr),.arlen(arlen),.arvalid(arvalid),.arready(arready),
        .rdata(rdata),.rvalid(rvalid),.rlast(rlast),.rid(rid),
        .byte_valid(byte_valid),.byte_ready(byte_ready),.byte_done(byte_done),.byte_data(byte_data),
        .idle(exporter_idle),.done(exporter_done),.failed(exporter_failed),.fault(exporter_fault));
    always @(posedge core_clk) begin
        if(!local_rst_n) begin
            state<=IDLE;transaction_active<=0;reset_wait<=0;held_base<=0;
            held_frame_id<=0;held_camera_id<=0;held_eye<=0;done<=0;failed<=0;fault<=0;
        end else begin
            done<=0;
            case(state)
                IDLE,COMPLETE: if(request_valid && request_ready) begin
                    if(!valid_layout) begin failed<=1;fault<=8'h40;state<=FAULT;end
                    else begin
                        held_base<=request_base_address;held_frame_id<=request_frame_id;
                        held_camera_id<=request_camera_id;held_eye<=request_eye;
                        transaction_active<=0;reset_wait<=0;state<=RESET_TRANSACTION;
                    end
                end
                RESET_TRANSACTION: if(reset_wait==15) begin transaction_active<=1;state<=CAPTURE;end
                                   else reset_wait<=reset_wait+1'b1;
                CAPTURE: if(writer_done) state<=START_EXPORT;
                START_EXPORT: state<=EXPORT;
                EXPORT: if(exporter_done) begin done<=1;state<=COMPLETE;end
                FAULT: state<=FAULT;
                default: begin failed<=1;fault<=8'hFF;state<=FAULT;end
            endcase
            if(transaction_active && (writer_failed || exporter_failed)) begin
                failed<=1;fault<=writer_failed ? writer_fault:exporter_fault;state<=FAULT;
            end
        end
    end
endmodule
