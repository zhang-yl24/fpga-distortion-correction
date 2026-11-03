`timescale 1ns/1ps
// Development-only processing transaction over four DDR banks. Address units
// are 4B, NOT bytes: STRIDE=0x100000 units is 4MiB. Source DMA is external;
// commit is permitted only after the complete native frame was written/drained.
// Results are published only after engine done/CRC and locked until display_done.
module hdmi_camera_fisheye_bank #(
    parameter WIDTH=1920,HEIGHT=1080,BANK_STRIDE=1048576
)(
    input clk,rst_n,
    input source_valid,output source_ready,input source_bank,input [31:0] source_id,
    output [1:0] source_writable,output reg source_released,output reg released_bank,
    input display_request_valid,output display_request_ready,
    output reg display_grant_valid,input display_grant_ready,
    output reg [27:0] display_base,output reg [31:0] display_crc,display_id,
    input display_done_valid,input display_done_bank,
    input cfg_corrected,
    output [27:0] araddr,awaddr,output [3:0] arlen,awlen,
    output arvalid,awvalid,input arready,awready,
    input [255:0] rdata,input rvalid,rlast,input [3:0] rid,
    output [255:0] wdata,output [31:0] wstrb,input wready,wlast,
    output reg processing,pending,display_active,output reg write_bank,front_bank,
    output reg [31:0] completed_frames,last_cycles,
    output [31:0] hits,misses,queries,output failed,output [7:0] fault
);
    localparam FRAME_UNITS=WIDTH*HEIGHT/2;
    localparam LAYOUT_OK=WIDTH>=16 && HEIGHT>=8 && WIDTH<=8192 && HEIGHT<=8192 &&
        WIDTH*HEIGHT<=16777216 && WIDTH%16==0 && HEIGHT%8==0 && WIDTH*HEIGHT%256==0 &&
        BANK_STRIDE>=FRAME_UNITS && BANK_STRIDE%128==0 && BANK_STRIDE<=67108864;
    reg active_source,active_corrected,front_valid,ownership_fault;
    reg [31:0] accepted_id,pending_crc,front_crc,pending_id,front_id,cycles;
    reg start;
    wire engine_ready,engine_done,engine_failed;
    wire [7:0] engine_fault;
    wire [27:0] completed_base;
    wire [31:0] engine_id,engine_crc;
    wire [27:0] source_base=active_source ? BANK_STRIDE:0;
    wire [27:0] result_base=write_bank ? 3*BANK_STRIDE:2*BANK_STRIDE;
    // A producer offering a completed frame retains it while !source_ready.
    // Do not advertise that offered bank as reusable by a future input DMA.
    wire [1:0] read_lock=processing ? (active_source ? 2'b10:2'b01):2'b00;
    wire [1:0] offered_lock=source_valid ? (source_bank ? 2'b10:2'b01):2'b00;
    assign source_writable=(rst_n && LAYOUT_OK && !failed) ? ~(read_lock|offered_lock):2'b00;
    assign source_ready=LAYOUT_OK && !failed && !processing && !pending && !start && engine_ready &&
        (!display_active || write_bank!=front_bank);
    assign display_request_ready=LAYOUT_OK && !failed && !display_active && !display_grant_valid && (pending || front_valid);
    assign failed=ownership_fault || engine_failed;
    assign fault=ownership_fault ? 8'h71:engine_fault;
    hdmi_camera_fisheye_engine_tile8 #(.WIDTH(WIDTH),.HEIGHT(HEIGHT)) engine(
        .clk(clk),.rst_n(rst_n),.frame_valid(start),.frame_ready(engine_ready),.cfg_corrected(active_corrected),
        .source_base(source_base),.output_base(result_base),.frame_id(accepted_id),
        .araddr(araddr),.arlen(arlen),.arvalid(arvalid),.arready(arready),.rdata(rdata),.rvalid(rvalid),.rlast(rlast),.rid(rid),
        .awaddr(awaddr),.awlen(awlen),.awvalid(awvalid),.awready(awready),.wdata(wdata),.wstrb(wstrb),.wready(wready),.wlast(wlast),
        .done(engine_done),.failed(engine_failed),.fault(engine_fault),.completed_base(completed_base),
        .completed_id(engine_id),.completed_crc(engine_crc),.hits(hits),.misses(misses),.completed_queries(queries));
    always @(posedge clk) begin
        if(!rst_n) begin
            processing<=0;pending<=0;display_active<=0;write_bank<=0;front_bank<=1;front_valid<=0;
            active_source<=0;active_corrected<=1;ownership_fault<=0;source_released<=0;released_bank<=0;accepted_id<=0;
            pending_crc<=0;front_crc<=0;pending_id<=0;front_id<=0;cycles<=0;start<=0;
            display_grant_valid<=0;display_base<=0;display_crc<=0;display_id<=0;completed_frames<=0;last_cycles<=0;
        end else begin
            start<=0;source_released<=0;
            if(!LAYOUT_OK) ownership_fault<=1;
            if(source_valid && source_ready) begin
                active_source<=source_bank;active_corrected<=cfg_corrected;accepted_id<=source_id;processing<=1;cycles<=0;start<=1;
            end
            if(processing) cycles<=cycles+1'b1;
            if(engine_done) begin
                if(!processing || pending || completed_base!=result_base || engine_id!=accepted_id)
                    ownership_fault<=1;
                else begin
                    processing<=0;pending<=1;pending_crc<=engine_crc;pending_id<=engine_id;
                    source_released<=1;released_bank<=active_source;completed_frames<=completed_frames+1'b1;last_cycles<=cycles;
                end
            end
            if(display_request_valid && display_request_ready) begin
                display_active<=1;display_grant_valid<=1;
                if(pending) begin
                    front_bank<=write_bank;front_valid<=1;front_crc<=pending_crc;front_id<=pending_id;
                    display_base<=result_base;display_crc<=pending_crc;display_id<=pending_id;
                    write_bank<=!write_bank;pending<=0;
                end else begin
                    display_base<=front_bank ? 3*BANK_STRIDE:2*BANK_STRIDE;display_crc<=front_crc;display_id<=front_id;
                end
            end
            if(display_grant_valid && display_grant_ready) display_grant_valid<=0;
            if(display_done_valid) begin
                if(!display_active || display_grant_valid || display_done_bank!=front_bank) ownership_fault<=1;
                else display_active<=0;
            end
            if(processing && display_active && write_bank==front_bank) ownership_fault<=1;
        end
    end
endmodule
