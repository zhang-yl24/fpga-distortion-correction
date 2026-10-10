`timescale 1ns/1ps
// Two-bank ownership: writer -> pending -> frame-boundary reader -> free.
// Writer pauses while a complete bank is pending; this bounds throughput to
// capture/hand-off cadence but never overwrites the displayed frame.
module ddr_live_video #(
    parameter WIDTH=640,HEIGHT=480,BANK_STRIDE=262144,
    HT=1650,VT=750,HS=40,VS=5,X0=260,Y0=25,AW=1280,AH=720
)(
    input cam_clk,core_clk,pix_clk,rst_n,ready,
    input vsync,href,input [7:0] data,
    output wire [27:0] awaddr,araddr,output wire [3:0] awlen,arlen,
    output wire awvalid,arvalid,input awready,arready,
    output wire [255:0] wdata,output wire [31:0] wstrb,input wready,wlast,
    input [255:0] rdata,input rvalid,rlast,input [3:0] rid,
    output wire hs,vs,de,output wire [7:0] r,g,b,
    output wire display_valid,output wire [31:0] output_frames,underflows,pixel_mismatches,pixel_checksum,
    output reg [31:0] captured_frames,ownership_errors,
    output wire [31:0] read_frames,read_checksum,
    output reg [31:0] latest_source_checksum,
    output wire failed,output wire [7:0] fault
);
    localparam FRAME_BEATS=WIDTH*HEIGHT/16;
    (* async_reg="true" *) reg [1:0] reset_sync=0;
    always @(posedge core_clk or negedge rst_n)
        if(!rst_n) reset_sync<=0;else reset_sync<={reset_sync[0],1'b1};
    wire core_rst_n=reset_sync[1];
    reg capture_active,write_bank,pending,front_bank,front_valid;
    reg [31:0] front_checksum;
    reg [6:0] restart_wait;
    wire capture_rst_n=rst_n && capture_active;
    wire writer_done,writer_failed;wire [7:0] writer_fault;
    wire [31:0] written_beats,write_checksum,source_checksum;
    wire source_done,source_valid;
    wire [9:0] cap_available;wire cap_ready,cap_valid,cap_pop;
    wire [257:0] cap_data;
    camera_live_bridge #(.WIDTH(WIDTH),.HEIGHT(HEIGHT)) bridge(
        .cam_clk(cam_clk),.ddr_clk(core_clk),.rst_n(capture_rst_n),.arm(ready),
        .vsync(vsync),.href(href),.data(data),.fifo_rd_en(cap_pop),.fifo_data(cap_data),
        .fifo_valid(cap_valid),.fifo_ready(cap_ready),.fifo_available(cap_available),
        .source_done(source_done),.source_valid(source_valid),.source_checksum(source_checksum));
    wire [27:0] write_base=write_bank ? BANK_STRIDE:0;
    ddr_video_writer #(.FRAME_BEATS(FRAME_BEATS)) writer(
        .clk(core_clk),.rst_n(core_rst_n && capture_active && ready),.base_address(write_base),
        .fifo_available(cap_available),.fifo_ready(cap_ready),.fifo_rd_en(cap_pop),.fifo_valid(cap_valid),.fifo_data(cap_data),
        .source_done(source_done),.source_valid(source_valid),.source_checksum(source_checksum),
        .awaddr(awaddr),.awlen(awlen),.awvalid(awvalid),.awready(awready),
        .wdata(wdata),.wstrb(wstrb),.wready(wready),.wlast(wlast),
        .state(),.done(writer_done),.failed(writer_failed),.fault(writer_fault),
        .written_beats(written_beats),.write_checksum(write_checksum));
    wire request_toggle;
    reg grant_toggle,grant_valid,reader_start;
    reg [31:0] grant_checksum,reader_expected;
    reg [27:0] reader_base;
    (* async_reg="true" *) reg [1:0] request_sync=0;
    reg request_seen;
    wire reader_idle,reader_done,reader_failed;wire [7:0] reader_fault;
    wire [9:0] display_used,display_available;
    wire display_wr_ready,display_rd_ready,display_valid_data,display_push,display_pop;
    wire [255:0] display_write_data,display_read_data;
    wire [31:0] read_beats;
    ddr_video_reader #(.FRAME_BEATS(FRAME_BEATS)) reader(
        .clk(core_clk),.rst_n(core_rst_n && ready),.start(reader_start),
        .base_address(reader_base),.expected_checksum(reader_expected),
        .fifo_used(display_used),.fifo_ready(display_wr_ready),.fifo_wr_en(display_push),.fifo_data(display_write_data),
        .araddr(araddr),.arlen(arlen),.arvalid(arvalid),.arready(arready),
        .rdata(rdata),.rvalid(rvalid),.rlast(rlast),.rid(rid),
        .idle(reader_idle),.done(reader_done),.failed(reader_failed),.fault(reader_fault),
        .read_beats(read_beats),.last_checksum(read_checksum),.completed_frames(read_frames));
    video_async_fifo display_fifo(.wr_clk(core_clk),.rd_clk(pix_clk),.rst_n(rst_n),
        .wr_en(display_push),.wr_data(display_write_data),.wr_full(),.wr_ready(display_wr_ready),.wr_used(display_used),
        .rd_en(display_pop),.rd_data(display_read_data),.rd_valid(display_valid_data),
        .rd_empty(),.rd_ready(display_rd_ready),.rd_available(display_available));
    ddr_video_output #(.WIDTH(WIDTH),.HEIGHT(HEIGHT),.HT(HT),.VT(VT),.HS(HS),.VS(VS),.X0(X0),.Y0(Y0),.AW(AW),.AH(AH))
    output_video(.clk(pix_clk),.rst_n(rst_n),.request_toggle(request_toggle),
        .grant_toggle(grant_toggle),.grant_valid(grant_valid),.grant_checksum(grant_checksum),
        .fifo_ready(display_rd_ready),.fifo_valid(display_valid_data),.fifo_data(display_read_data),.fifo_rd_en(display_pop),
        .hs(hs),.vs(vs),.de(de),.r(r),.g(g),.b(b),.display_valid(display_valid),.result_toggle(),
        .completed_frames(output_frames),.underflows(underflows),.mismatches(pixel_mismatches),.last_checksum(pixel_checksum));
    reg ownership_failed;
    assign failed=writer_failed || reader_failed || ownership_failed;
    assign fault=ownership_failed ? 8'h31:writer_failed ? writer_fault:reader_failed ? reader_fault:8'h00;
    always @(posedge core_clk) begin
        if(!core_rst_n) begin
            capture_active<=0;write_bank<=0;pending<=0;front_bank<=1;front_valid<=0;front_checksum<=0;
            restart_wait<=0;captured_frames<=0;ownership_errors<=0;ownership_failed<=0;latest_source_checksum<=0;
            grant_toggle<=0;grant_valid<=0;grant_checksum<=0;reader_base<=0;reader_expected<=0;
            reader_start<=0;request_sync<=0;request_seen<=0;
        end else begin
            request_sync<={request_sync[0],request_toggle};reader_start<=0;
            if(ready && !capture_active && !pending && !failed) begin
                if(restart_wait==64) begin capture_active<=1;restart_wait<=0;end
                else restart_wait<=restart_wait+1'b1;
            end
            if(capture_active && writer_done) begin
                pending<=1;capture_active<=0;captured_frames<=captured_frames+1'b1;latest_source_checksum<=source_checksum;
            end
            if(request_sync[1]!=request_seen) begin
                request_seen<=request_sync[1];grant_toggle<=request_sync[1];grant_valid<=0;
                if(ready && !failed && (front_valid || pending)) begin
                    if(!reader_idle) begin ownership_failed<=1;ownership_errors<=ownership_errors+1'b1;end
                    else begin
                        grant_valid<=1;reader_start<=1;
                        if(pending) begin
                            front_bank<=write_bank;front_valid<=1;front_checksum<=latest_source_checksum;
                            reader_base<=write_bank ? BANK_STRIDE:0;reader_expected<=latest_source_checksum;grant_checksum<=latest_source_checksum;
                            write_bank<=!write_bank;pending<=0;restart_wait<=0;
                        end else begin
                            reader_base<=front_bank ? BANK_STRIDE:0;reader_expected<=front_checksum;grant_checksum<=front_checksum;
                        end
                    end
                end
            end
            // Invariant valid during active DDR operations, including simultaneous
            // reads and writes. Never depend on apparent pixel-clock phase.
            if(capture_active && front_valid && write_bank==front_bank) begin
                ownership_failed<=1;ownership_errors<=ownership_errors+1'b1;
            end
        end
    end
endmodule
