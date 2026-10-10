`timescale 1ns/1ps
// Source banks 0/1 alternate: capture may write only the bank not being read. Result banks 2/3
// alternate through processing -> pending -> frame-boundary front -> free.
// No coordinate lookup table: staged coefficients feed the arithmetic core.
module ddr_adaptive_video #(
    parameter WIDTH=640,HEIGHT=480,BANK_STRIDE=262144,MAX_RADIUS_Q22=0,CAPTURE_OVERLAP=1,
    HT=1650,VT=750,HS=40,VS=5,X0=260,Y0=25,AW=1280,AH=720
)(
    input cam_clk,core_clk,pix_clk,rst_n,ready,
    input vsync,href,input [7:0] data,
    input signed [23:0] cfg_out_cx,cfg_out_cy,cfg_src_cx,cfg_src_cy,cfg_src_fx,cfg_src_fy,
    input signed [31:0] cfg_inv_fx,cfg_inv_fy,cfg_k1,cfg_k2,cfg_k3,cfg_p1,cfg_p2,
    input cfg_rotation_valid,input [31:0] cfg_rotation_phase,
    input signed [23:0] cfg_rot_cx,cfg_rot_cy,input signed [31:0] cfg_rot_cos,cfg_rot_sin,
    output reg [31:0] result_phase,
    output reg [31:0] processed_frames,last_process_cycles,
    output wire [31:0] cache_hits,cache_misses,completed_queries,
    output reg [31:0] latest_result_checksum,
    output wire [27:0] awaddr,araddr,output wire [3:0] awlen,arlen,
    output wire awvalid,arvalid,input awready,arready,
    output wire [255:0] wdata,output wire [31:0] wstrb,input wready,wlast,
    input [255:0] rdata,input rvalid,rlast,input [3:0] rid,
    output wire hs,vs,de,output wire [7:0] r,g,b,
    output wire display_valid,output wire [31:0] output_frames,underflows,pixel_mismatches,pixel_checksum,
    output reg [31:0] capture_overlap_cycles,last_capture_cycles,source_bank_wait_cycles,
    output reg [31:0] captured_frames,ownership_errors,
    output wire [31:0] read_frames,read_checksum,
    output reg [31:0] latest_source_checksum,
    output wire failed,output wire [7:0] fault
);
    localparam FRAME_BEATS=WIDTH*HEIGHT/16;
    localparam VALID_BANK_LAYOUT=WIDTH>=8 && WIDTH<=4095 && HEIGHT>=8 && HEIGHT<=4095 && WIDTH%8==0 && HEIGHT%8==0 && BANK_STRIDE>=WIDTH*HEIGHT/2 && BANK_STRIDE%128==0 && BANK_STRIDE<=67108864;
    (* async_reg="true" *) reg [1:0] reset_sync=0;
    always @(posedge core_clk or negedge rst_n)
        if(!rst_n) reset_sync<=0;else reset_sync<={reset_sync[0],1'b1};
    wire core_rst_n=reset_sync[1];
    reg capture_active,write_bank,pending,front_bank,front_valid;
    reg [31:0] front_checksum,pending_checksum,source_id;
    reg source_pending,processing,engine_start;
    reg capture_bank,pending_source_bank,processing_source_bank;
    reg [31:0] processing_id,capture_cycles;
    reg [31:0] process_cycles,accepted_phase;
    wire engine_ready,engine_done,engine_failed,read_arb_failed,write_arb_failed;
    wire [7:0] engine_fault,read_arb_fault,write_arb_fault;
    wire [31:0] engine_crc,engine_id;
    wire [27:0] engine_base;
    wire [27:0] camera_awaddr,result_awaddr,display_araddr,sample_araddr;
    wire [3:0] camera_awlen,result_awlen,display_arlen,sample_arlen;
    wire camera_awvalid,camera_awready,result_awvalid,result_awready;
    wire display_arvalid,display_arready,sample_arvalid,sample_arready;
    wire [255:0] camera_wdata,result_wdata,display_rdata,sample_rdata;
    wire [31:0] camera_wstrb,result_wstrb;
    wire camera_wready,camera_wlast,result_wready,result_wlast;
    wire display_rvalid,display_rlast,sample_rvalid,sample_rlast;
    wire [3:0] display_rid,sample_rid;
    reg [6:0] restart_wait;
    wire capture_rst_n=rst_n && capture_active;
    wire writer_done,writer_failed;wire [7:0] writer_fault;
    wire [31:0] written_beats,write_checksum,source_checksum;
    wire source_done,source_valid;
    wire [9:0] cap_available;wire cap_ready,cap_valid,cap_pop;
    wire [257:0] cap_data;
    camera_live_bridge_early #(.WIDTH(WIDTH),.HEIGHT(HEIGHT)) bridge(
        .cam_clk(cam_clk),.ddr_clk(core_clk),.rst_n(capture_rst_n),.arm(ready),
        .vsync(vsync),.href(href),.data(data),.fifo_rd_en(cap_pop),.fifo_data(cap_data),
        .fifo_valid(cap_valid),.fifo_ready(cap_ready),.fifo_available(cap_available),
        .source_done(source_done),.source_valid(source_valid),.source_checksum(source_checksum));
    wire [27:0] write_base=capture_bank ? BANK_STRIDE:0;
    ddr_video_writer #(.FRAME_BEATS(FRAME_BEATS)) writer(
        .clk(core_clk),.rst_n(core_rst_n && capture_active && ready),.base_address(write_base),
        .fifo_available(cap_available),.fifo_ready(cap_ready),.fifo_rd_en(cap_pop),.fifo_valid(cap_valid),.fifo_data(cap_data),
        .source_done(source_done),.source_valid(source_valid),.source_checksum(source_checksum),
        .awaddr(camera_awaddr),.awlen(camera_awlen),.awvalid(camera_awvalid),.awready(camera_awready),
        .wdata(camera_wdata),.wstrb(camera_wstrb),.wready(camera_wready),.wlast(camera_wlast),
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
        .araddr(display_araddr),.arlen(display_arlen),.arvalid(display_arvalid),.arready(display_arready),
        .rdata(display_rdata),.rvalid(display_rvalid),.rlast(display_rlast),.rid(display_rid),
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
    wire transaction_rst_n=core_rst_n && ready;
    wire [27:0] result_base=write_bank ? 3*BANK_STRIDE:2*BANK_STRIDE;
    wire [27:0] processing_source_base=processing_source_bank ? BANK_STRIDE:0;
    adaptive_tiled_frame_engine #(.WIDTH(WIDTH),.HEIGHT(HEIGHT),.MAX_RADIUS_Q22(MAX_RADIUS_Q22)) engine(
        .clk(core_clk),.rst_n(transaction_rst_n),.frame_valid(engine_start),.frame_ready(engine_ready),
        .source_base(processing_source_base),.output_base(result_base),.frame_id(processing_id),
        .cfg_out_cx(cfg_out_cx),.cfg_out_cy(cfg_out_cy),.cfg_src_cx(cfg_src_cx),.cfg_src_cy(cfg_src_cy),
        .cfg_src_fx(cfg_src_fx),.cfg_src_fy(cfg_src_fy),.cfg_inv_fx(cfg_inv_fx),.cfg_inv_fy(cfg_inv_fy),
        .cfg_k1(cfg_k1),.cfg_k2(cfg_k2),.cfg_k3(cfg_k3),.cfg_p1(cfg_p1),.cfg_p2(cfg_p2),
        .cfg_rot_cx(cfg_rot_cx),.cfg_rot_cy(cfg_rot_cy),.cfg_rot_cos(cfg_rot_cos),.cfg_rot_sin(cfg_rot_sin),
        .araddr(sample_araddr),.arlen(sample_arlen),.arvalid(sample_arvalid),.arready(sample_arready),
        .rdata(sample_rdata),.rvalid(sample_rvalid),.rlast(sample_rlast),.rid(sample_rid),
        .awaddr(result_awaddr),.awlen(result_awlen),.awvalid(result_awvalid),.awready(result_awready),
        .wdata(result_wdata),.wstrb(result_wstrb),.wready(result_wready),.wlast(result_wlast),
        .done(engine_done),.failed(engine_failed),.fault(engine_fault),
        .completed_base(engine_base),.completed_id(engine_id),.completed_crc(engine_crc),
        .hits(cache_hits),.misses(cache_misses),.completed_queries(completed_queries));
    ddr_read_arbiter read_bus(.clk(core_clk),.rst_n(transaction_rst_n),.display_urgent(display_used<64),
        .c0_araddr(display_araddr),.c1_araddr(sample_araddr),.c0_arlen(display_arlen),.c1_arlen(sample_arlen),
        .c0_arvalid(display_arvalid),.c1_arvalid(sample_arvalid),.c0_arready(display_arready),.c1_arready(sample_arready),
        .c0_rdata(display_rdata),.c1_rdata(sample_rdata),.c0_rvalid(display_rvalid),.c1_rvalid(sample_rvalid),
        .c0_rlast(display_rlast),.c1_rlast(sample_rlast),.c0_rid(display_rid),.c1_rid(sample_rid),
        .araddr(araddr),.arlen(arlen),.arvalid(arvalid),.arready(arready),
        .rdata(rdata),.rvalid(rvalid),.rlast(rlast),.rid(rid),
        .failed(read_arb_failed),.fault(read_arb_fault),.busy(),.bursts0(),.bursts1());
    ddr_write_arbiter write_bus(.clk(core_clk),.rst_n(transaction_rst_n),
        .c0_awaddr(camera_awaddr),.c1_awaddr(result_awaddr),.c0_awlen(camera_awlen),.c1_awlen(result_awlen),
        .c0_awvalid(camera_awvalid),.c1_awvalid(result_awvalid),.c0_awready(camera_awready),.c1_awready(result_awready),
        .c0_wdata(camera_wdata),.c1_wdata(result_wdata),.c0_wstrb(camera_wstrb),.c1_wstrb(result_wstrb),
        .c0_wready(camera_wready),.c1_wready(result_wready),.c0_wlast(camera_wlast),.c1_wlast(result_wlast),
        .awaddr(awaddr),.awlen(awlen),.awvalid(awvalid),.awready(awready),
        .wdata(wdata),.wstrb(wstrb),.wready(wready),.wlast(wlast),
        .failed(write_arb_failed),.fault(write_arb_fault),.busy(),.bursts0(),.bursts1());
    reg ownership_failed;
    assign failed=writer_failed || reader_failed || engine_failed || read_arb_failed || write_arb_failed || ownership_failed;
    assign fault=ownership_failed ? 8'h31:engine_failed ? engine_fault:read_arb_failed ? (8'h50|read_arb_fault):
        write_arb_failed ? (8'h60|write_arb_fault):writer_failed ? writer_fault:reader_failed ? reader_fault:8'h00;
    always @(posedge core_clk) begin
        if(!core_rst_n) begin
            capture_active<=0;write_bank<=0;pending<=0;front_bank<=1;front_valid<=0;front_checksum<=0;
            restart_wait<=0;captured_frames<=0;ownership_errors<=0;ownership_failed<=0;latest_source_checksum<=0;
            capture_bank<=0;pending_source_bank<=0;processing_source_bank<=0;processing_id<=0;capture_cycles<=0;
            capture_overlap_cycles<=0;last_capture_cycles<=0;source_bank_wait_cycles<=0;
            grant_toggle<=0;grant_valid<=0;grant_checksum<=0;reader_base<=0;reader_expected<=0;
            reader_start<=0;request_sync<=0;request_seen<=0;
            source_pending<=0;processing<=0;engine_start<=0;pending_checksum<=0;source_id<=0;
            processed_frames<=0;last_process_cycles<=0;process_cycles<=0;result_phase<=0;accepted_phase<=0;latest_result_checksum<=0;
        end else begin
            request_sync<={request_sync[0],request_toggle};reader_start<=0;engine_start<=0;
            if(capture_active) capture_cycles<=capture_cycles+1'b1;
            if(capture_active && processing) capture_overlap_cycles<=capture_overlap_cycles+1'b1;
            if(!capture_active && (source_pending || (processing && capture_bank==processing_source_bank)))
                source_bank_wait_cycles<=source_bank_wait_cycles+1'b1;
            if(VALID_BANK_LAYOUT && ready && !capture_active && !source_pending &&
               (!processing || (CAPTURE_OVERLAP && capture_bank!=processing_source_bank)) && !failed) begin
                if(restart_wait==64) begin capture_active<=1;restart_wait<=0;capture_cycles<=0;end
                else restart_wait<=restart_wait+1'b1;
            end
            if(capture_active && writer_done) begin
                source_pending<=1;capture_active<=0;captured_frames<=captured_frames+1'b1;
                pending_source_bank<=capture_bank;capture_bank<=!capture_bank;last_capture_cycles<=capture_cycles;
                latest_source_checksum<=source_checksum;source_id<=captured_frames+1'b1;
            end
            if(ready && source_pending && !processing && !pending && engine_ready && cfg_rotation_valid && !failed) begin
                source_pending<=0;processing<=1;engine_start<=1;process_cycles<=0;
                processing_source_bank<=pending_source_bank;processing_id<=source_id;
            end
            if(engine_start && engine_ready) accepted_phase<=cfg_rotation_phase;
            if(processing) process_cycles<=process_cycles+1'b1;
            if(processing && engine_done && !failed) begin
                processing<=0;pending<=1;result_phase<=accepted_phase;pending_checksum<=engine_crc;latest_result_checksum<=engine_crc;
                processed_frames<=processed_frames+1'b1;last_process_cycles<=process_cycles;restart_wait<=0;
                if(engine_base!=result_base || engine_id!=processing_id) begin
                    ownership_failed<=1;ownership_errors<=ownership_errors+1'b1;
                end
            end
            if(request_sync[1]!=request_seen) begin
                request_seen<=request_sync[1];grant_toggle<=request_sync[1];grant_valid<=0;
                if(ready && !failed && (front_valid || pending)) begin
                    if(!reader_idle) begin ownership_failed<=1;ownership_errors<=ownership_errors+1'b1;end
                    else begin
                        grant_valid<=1;reader_start<=1;
                        if(pending) begin
                            front_bank<=write_bank;front_valid<=1;front_checksum<=pending_checksum;
                            reader_base<=result_base;reader_expected<=pending_checksum;grant_checksum<=pending_checksum;
                            write_bank<=!write_bank;pending<=0;
                        end else begin
                            reader_base<=front_bank ? 3*BANK_STRIDE:2*BANK_STRIDE;
                            reader_expected<=front_checksum;grant_checksum<=front_checksum;
                        end
                    end
                end
            end
            if(!VALID_BANK_LAYOUT || (capture_active && (source_pending || (processing && capture_bank==processing_source_bank))) ||
               (source_pending && processing && pending_source_bank==processing_source_bank) ||
               (processing && front_valid && write_bank==front_bank)) begin
                ownership_failed<=1;ownership_errors<=ownership_errors+1'b1;
            end
        end
    end
endmodule
