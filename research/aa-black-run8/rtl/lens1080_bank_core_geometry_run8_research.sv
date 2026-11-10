`timescale 1ns/1ps
// Development-only processing transaction over four DDR banks. Address units
// are 4B, NOT bytes: STRIDE=0x100000 units is 4MiB. Source DMA is external;
// commit is permitted only after the complete native frame was written/drained.
// Results are published only after engine done/CRC and locked until display_done.
// OPT-IN RESEARCH ONLY; no physical-equivalence or board-adoption claim.
module lens1080_bank_core_geometry_run8_research #(
    parameter BLACK_RUN8_RESEARCH=0,
    parameter WIDTH=1920,HEIGHT=1080,BANK_STRIDE=1048576,MAX_RADIUS_Q22=8388608,STATS_ENABLE=0,RASTER_DOUBLE_BUFFER=0,CACHE_PROFILE=0,HDMI_FISHEYE_PROFILE=0,TILE8_GROUP_WIDTH=16,RATIONAL_BROWN_PROFILE=0,MACRO_TILE_HEIGHT=8,CACHE_INDEX_BITS=6,PREFETCH_QUERY_DEPTH=0,PREFETCH_LOOKAHEAD=256,CACHE_ROW_STRIDE=0,CACHE_HEAD_PREDECODE=1,CRC_FOLD_BITS=1,READ_REQUEST_LOOKAHEAD=0,RESULT_BANKS=2
)(
    output [27:0] completed_source_base,
    output [31:0] completed_param_id,
    output completed_correction_enable,completed_gamma_enable,completed_compressed,
    output signed [31:0] completed_rot_cos,completed_rot_sin,
    input clk,rst_n,
    input gamma_enable,correction_enable,
    input [31:0] telemetry_param_id,
    output reg [31:0] display_param_id,output reg [7:0] display_mode,
    input source_valid,output source_ready,input source_bank,input [31:0] source_id,
    output [1:0] source_writable,output reg source_released,output reg released_bank,
    input display_request_valid,output display_request_ready,
    output reg display_grant_valid,input display_grant_ready,
    output reg [27:0] display_base,output reg [31:0] display_crc,display_id,
    input display_done_valid,input display_done_bank,
    input signed [23:0] cfg_out_cx,cfg_out_cy,cfg_src_cx,cfg_src_cy,cfg_src_fx,cfg_src_fy,
    input signed [31:0] cfg_inv_fx,cfg_inv_fy,cfg_k1,cfg_k2,cfg_k3,cfg_p1,cfg_p2,
    input signed [23:0] cfg_rot_cx,cfg_rot_cy,
    input signed [31:0] cfg_rot_cos,cfg_rot_sin,
    output [27:0] araddr,awaddr,output [3:0] arlen,awlen,
    output arvalid,awvalid,input arready,awready,
    input [255:0] rdata,input rvalid,rlast,input [3:0] rid,
    output [255:0] wdata,output [31:0] wstrb,input wready,wlast,
    output reg processing,pending,display_active,output reg write_bank,front_bank,
    output reg [31:0] completed_frames,last_cycles,
    output reg stats_last_valid,output reg [31:0] stats_last_id,stats_last_param_id,stats_last_mode,
    output [31:0] hits,misses,queries,output failed,output [7:0] fault
);
    localparam FRAME_UNITS=WIDTH*HEIGHT/2;
    localparam STATIC_COMPATIBLE=BLACK_RUN8_RESEARCH==1 && WIDTH==1920 && HEIGHT==1080 &&
            MAX_RADIUS_Q22==0 && RASTER_DOUBLE_BUFFER==0 && CACHE_PROFILE==6 &&
            HDMI_FISHEYE_PROFILE==0 && TILE8_GROUP_WIDTH==64 && RATIONAL_BROWN_PROFILE==1 &&
            MACRO_TILE_HEIGHT==32 && CACHE_INDEX_BITS==7 && PREFETCH_QUERY_DEPTH==4096 &&
            PREFETCH_LOOKAHEAD==512 && CACHE_ROW_STRIDE==2 && CACHE_HEAD_PREDECODE==1 &&
            CRC_FOLD_BITS==2 && READ_REQUEST_LOOKAHEAD==0 && RESULT_BANKS==2;
    localparam LAYOUT_OK=(!BLACK_RUN8_RESEARCH || STATIC_COMPATIBLE) && WIDTH>=16 && HEIGHT>=8 && WIDTH<=8192 && HEIGHT<=8192 &&
        WIDTH*HEIGHT<=16777216 && WIDTH%16==0 && HEIGHT%8==0 && WIDTH*HEIGHT%256==0 &&
        BANK_STRIDE>=FRAME_UNITS && BANK_STRIDE%128==0 && BANK_STRIDE<=67108864;
    reg active_source,front_valid,ownership_fault;
    reg [31:0] accepted_id,pending_crc,front_crc,pending_id,front_id,cycles;
    reg start;
    reg [31:0] frame_param_id,pending_param_id,front_param_id;
    reg [7:0] pending_mode,front_mode;
    // Configuration belongs to the accepted source transaction. A producer
    // may change ALL cfg fields after source_valid && source_ready;
    // the private engine start pulse occurs on the following cycle.
    // All 17 Brown/rotation fields form one 480-bit logical snapshot.
    reg signed [23:0] frame_out_cx,frame_out_cy,frame_src_cx,frame_src_cy,frame_src_fx,frame_src_fy;
    reg signed [31:0] frame_inv_fx,frame_inv_fy,frame_k1,frame_k2,frame_k3,frame_p1,frame_p2;
    reg signed [23:0] frame_rot_cx,frame_rot_cy;
    reg signed [31:0] frame_rot_cos,frame_rot_sin;
    always @(posedge clk) begin
        if(!rst_n) {frame_out_cx,frame_out_cy,frame_src_cx,frame_src_cy,frame_src_fx,frame_src_fy,frame_inv_fx,frame_inv_fy,frame_k1,frame_k2,frame_k3,frame_p1,frame_p2,frame_rot_cx,frame_rot_cy,frame_rot_cos,frame_rot_sin}<=0;
        else if(source_valid && source_ready)
            {frame_out_cx,frame_out_cy,frame_src_cx,frame_src_cy,frame_src_fx,frame_src_fy,frame_inv_fx,frame_inv_fy,frame_k1,frame_k2,frame_k3,frame_p1,frame_p2,frame_rot_cx,frame_rot_cy,frame_rot_cos,frame_rot_sin}<=
                {cfg_out_cx,cfg_out_cy,cfg_src_cx,cfg_src_cy,cfg_src_fx,cfg_src_fy,cfg_inv_fx,cfg_inv_fy,cfg_k1,cfg_k2,cfg_k3,cfg_p1,cfg_p2,cfg_rot_cx,cfg_rot_cy,cfg_rot_cos,cfg_rot_sin};
    end
    // Same reset and source-commit edge as all 17 Brown/rotation fields.
    // 482 logical payload bits (Brown13 + rotation4 + Gamma + geometry); mapped FF/resource cost is not measured here.
    reg frame_gamma_enable,frame_correction_enable;
    always @(posedge clk) begin
        if(!rst_n) begin frame_gamma_enable<=0;frame_correction_enable<=0;end
        else if(source_valid && source_ready) begin
            frame_gamma_enable<=gamma_enable;frame_correction_enable<=correction_enable;
        end
    end
    wire engine_ready,engine_done,engine_failed;
    wire [7:0] engine_fault;
    wire [27:0] completed_base;
    wire [31:0] engine_id,engine_crc,gamma_frames;
    wire [1:0] gamma_mode;
    wire [27:0] source_base=active_source ? BANK_STRIDE:0;
    wire [27:0] result_base=write_bank ? 3*BANK_STRIDE:2*BANK_STRIDE;
    // A producer offering a completed frame retains it while !source_ready.
    // Do not advertise that offered bank as reusable by a future input DMA.
    wire [1:0] read_lock=processing ? (active_source ? 2'b10:2'b01):2'b00;
    wire [1:0] offered_lock=source_valid ? (source_bank ? 2'b10:2'b01):2'b00;
    assign source_writable=(rst_n && LAYOUT_OK && !failed) ? ~(read_lock|offered_lock):2'b00;
    assign source_ready=(!BLACK_RUN8_RESEARCH || !early_owner_fault) && LAYOUT_OK && !failed && !processing && !pending && !start && engine_ready &&
        (!display_active || write_bank!=front_bank);
    // Completion is already identity/CRC-qualified by the engine on this edge.
    // Forward only when no older result is waiting. Never replace an older pending frame.
    // Independent engine completion identity. Qualifies SAME-edge publication
    // and source release, not just the subsequent sticky ownership fault.
    // Legacy branch has no independent extended identity; preserve its checks.
    wire extended_identity_ok=!BLACK_RUN8_RESEARCH || (
        completed_source_base==source_base && completed_param_id==frame_param_id &&
        completed_correction_enable==frame_correction_enable &&
        completed_gamma_enable==frame_gamma_enable && !completed_gamma_enable &&
        completed_rot_cos==frame_rot_cos && completed_rot_sin==frame_rot_sin &&
        completed_compressed==(frame_correction_enable && !frame_gamma_enable &&
            frame_rot_cos==32'sd1073741824 && frame_rot_sin==0));
    wire raw_completion_valid=extended_identity_ok &&engine_done && processing && !failed && !pending &&
        completed_base==result_base && engine_id==accepted_id &&
        gamma_mode!=2'd3 && (frame_gamma_enable || gamma_mode==2'd0);
    // Pure current-edge predicates, independent of final completion_valid.
    // Mirror sequential owner faults without a completion/early-fault loop.
    wire early_owner_fault=!LAYOUT_OK ||
        (display_done_valid && (!display_active || display_grant_valid || display_done_bank!=front_bank)) ||
        (processing && display_active && write_bank==front_bank) ||
        (engine_done && !raw_completion_valid);
    wire completion_valid=raw_completion_valid && (!BLACK_RUN8_RESEARCH || !early_owner_fault);
    assign display_request_ready=(!BLACK_RUN8_RESEARCH || !early_owner_fault) && LAYOUT_OK && !failed && !display_active && !display_grant_valid &&
        (pending || front_valid || completion_valid) &&
        // An invalid done is a fault on THIS edge, before sticky ownership_fault updates.
        // Do not issue even an old-front repeat grant on that edge.
        (!engine_done || completion_valid);
    assign failed=ownership_fault || engine_failed;
    assign fault=ownership_fault ? 8'h71:engine_fault;
    initial if(RESULT_BANKS!=2)$fatal(1,"R34 native integration supports RESULT_BANKS=2 only");
    // Every original static engine option is constrained to the exact variant.
    // STATS_ENABLE remains owner-only. BANK_STRIDE is checked by LAYOUT_OK;
    // variant address range/non-overlap guards remain in force.
    initial begin
        if(BLACK_RUN8_RESEARCH!=0 && BLACK_RUN8_RESEARCH!=1)
            $fatal(1,"BLACK_RUN8_RESEARCH must be 0 or 1");
        if(BLACK_RUN8_RESEARCH && !LAYOUT_OK)
            $fatal(1,"unsupported BLACK_RUN8_RESEARCH static configuration");
    end
    generate if(!BLACK_RUN8_RESEARCH) begin: g_legacy
    // Exact original engine instantiation preserved below, byte for byte.
    pipeline_gamma_frame_engine_1080_geometry_bypass #(.RATIONAL_BROWN_PROFILE(RATIONAL_BROWN_PROFILE),.MACRO_TILE_HEIGHT(MACRO_TILE_HEIGHT),.CACHE_INDEX_BITS(CACHE_INDEX_BITS),.PREFETCH_QUERY_DEPTH(PREFETCH_QUERY_DEPTH),.PREFETCH_LOOKAHEAD(PREFETCH_LOOKAHEAD),.CACHE_ROW_STRIDE(CACHE_ROW_STRIDE),.CACHE_HEAD_PREDECODE(CACHE_HEAD_PREDECODE),.CRC_FOLD_BITS(CRC_FOLD_BITS),.READ_REQUEST_LOOKAHEAD(READ_REQUEST_LOOKAHEAD),.HDMI_FISHEYE_PROFILE(HDMI_FISHEYE_PROFILE),.FORCE_TILE8(RATIONAL_BROWN_PROFILE ? 1:HDMI_FISHEYE_PROFILE),.TILE8_OVERLAP_WRITER(RATIONAL_BROWN_PROFILE ? 1:HDMI_FISHEYE_PROFILE),.CACHE_PROFILE(CACHE_PROFILE),.TILE8_GROUP_WIDTH(TILE8_GROUP_WIDTH),.WIDTH(WIDTH),.HEIGHT(HEIGHT),.MAX_RADIUS_Q22(MAX_RADIUS_Q22),.RASTER_DOUBLE_BUFFER(RASTER_DOUBLE_BUFFER)) engine(
        .clk(clk),.rst_n(rst_n),.frame_valid(start),.frame_ready(engine_ready),.gamma_enable(frame_gamma_enable),.correction_enable(frame_correction_enable),
        .gamma_mode(gamma_mode),.gamma_frames(gamma_frames),.source_base(source_base),.output_base(result_base),.frame_id(accepted_id),
        .cfg_out_cx(frame_out_cx),.cfg_out_cy(frame_out_cy),.cfg_src_cx(frame_src_cx),.cfg_src_cy(frame_src_cy),
        .cfg_src_fx(frame_src_fx),.cfg_src_fy(frame_src_fy),.cfg_inv_fx(frame_inv_fx),.cfg_inv_fy(frame_inv_fy),
        .cfg_k1(frame_k1),.cfg_k2(frame_k2),.cfg_k3(frame_k3),.cfg_p1(frame_p1),.cfg_p2(frame_p2),
        .cfg_rot_cx(frame_rot_cx),.cfg_rot_cy(frame_rot_cy),.cfg_rot_cos(frame_rot_cos),.cfg_rot_sin(frame_rot_sin),
        .araddr(araddr),.arlen(arlen),.arvalid(arvalid),.arready(arready),.rdata(rdata),.rvalid(rvalid),.rlast(rlast),.rid(rid),
        .awaddr(awaddr),.awlen(awlen),.awvalid(awvalid),.awready(awready),.wdata(wdata),.wstrb(wstrb),.wready(wready),.wlast(wlast),
        .done(engine_done),.failed(engine_failed),.fault(engine_fault),.completed_base(completed_base),
        .completed_id(engine_id),.completed_crc(engine_crc),.hits(hits),.misses(misses),.completed_queries(queries));
    // Compatibility telemetry only: NOT independent legacy completion evidence.
    assign completed_source_base=source_base;
    assign completed_param_id=frame_param_id;
    assign completed_correction_enable=frame_correction_enable;
    assign completed_gamma_enable=frame_gamma_enable;
    assign completed_rot_cos=frame_rot_cos;
    assign completed_rot_sin=frame_rot_sin;
    assign completed_compressed=1'b0;
    end else begin: g_run8
    assign gamma_mode=2'd0; // This variant rejects Gamma ON, never emulates it.
    pipeline_brown_run8_key1_research #(.ENABLE_BLACK_RUN8(1),.CRC_FOLD_BITS(CRC_FOLD_BITS)) engine(
        .clk(clk),.rst_n(rst_n),.frame_valid(start),.frame_ready(engine_ready),
        .correction_enable(frame_correction_enable),.gamma_enable(frame_gamma_enable),
        .cfg_rot_cos(frame_rot_cos),.cfg_rot_sin(frame_rot_sin),.param_id(frame_param_id),
        .source_base(source_base),.output_base(result_base),.frame_id(accepted_id),
        .completed_source_base(completed_source_base),.completed_param_id(completed_param_id),
        .completed_correction_enable(completed_correction_enable),.completed_gamma_enable(completed_gamma_enable),
        .completed_rot_cos(completed_rot_cos),.completed_rot_sin(completed_rot_sin),.completed_compressed(completed_compressed),
        .araddr(araddr),.arlen(arlen),.arvalid(arvalid),.arready(arready),.rdata(rdata),.rvalid(rvalid),.rlast(rlast),.rid(rid),
        .awaddr(awaddr),.awlen(awlen),.awvalid(awvalid),.awready(awready),.wdata(wdata),.wstrb(wstrb),.wready(wready),.wlast(wlast),
        .done(engine_done),.failed(engine_failed),.fault(engine_fault),.completed_base(completed_base),
        .completed_id(engine_id),.completed_crc(engine_crc),.hits(hits),.misses(misses),.completed_queries(queries),
        .logical_issued(),.logical_retired(),.scalar_issued(),.scalar_retired(),.gamma_frames(gamma_frames));
    end endgenerate
    always @(posedge clk) begin
        if(!rst_n) begin
            processing<=0;pending<=0;display_active<=0;write_bank<=0;front_bank<=1;front_valid<=0;
            active_source<=0;ownership_fault<=0;source_released<=0;released_bank<=0;accepted_id<=0;
            pending_crc<=0;front_crc<=0;pending_id<=0;front_id<=0;cycles<=0;start<=0;
            frame_param_id<=0;pending_param_id<=0;front_param_id<=0;display_param_id<=0;
            pending_mode<=0;front_mode<=0;display_mode<=0;
            display_grant_valid<=0;display_base<=0;display_crc<=0;display_id<=0;completed_frames<=0;last_cycles<=0;
            stats_last_valid<=0;stats_last_id<=0;stats_last_param_id<=0;stats_last_mode<=0;
        end else begin
            start<=0;source_released<=0;
            if(!LAYOUT_OK) ownership_fault<=1;
            if(source_valid && source_ready) begin
                active_source<=source_bank;accepted_id<=source_id;processing<=1;cycles<=0;start<=1;
                frame_param_id<=telemetry_param_id;
            end
            if(processing) cycles<=cycles+1'b1;
            if(engine_done) begin
                if(!completion_valid)
                    ownership_fault<=1;
                else begin
                    processing<=0;pending<=1;pending_crc<=engine_crc;pending_id<=engine_id;
                    pending_param_id<=frame_param_id;
                    pending_mode<={6'b0,frame_gamma_enable,frame_correction_enable};
                    source_released<=1;released_bank<=active_source;completed_frames<=completed_frames+1'b1;last_cycles<=cycles;
                    if(STATS_ENABLE)begin
                        stats_last_valid<=1;stats_last_id<=engine_id;stats_last_param_id<=frame_param_id;
                        stats_last_mode<={30'b0,frame_gamma_enable,frame_correction_enable};
                    end
                end
            end
            if(display_request_valid && display_request_ready) begin
                display_active<=1;display_grant_valid<=1;
                if(pending) begin
                    front_bank<=write_bank;front_valid<=1;front_crc<=pending_crc;front_id<=pending_id;
                    display_base<=result_base;display_crc<=pending_crc;display_id<=pending_id;
                    front_param_id<=pending_param_id;front_mode<=pending_mode;
                    display_param_id<=pending_param_id;display_mode<=pending_mode;
                    write_bank<=!write_bank;pending<=0;
                end else if(completion_valid) begin
                    // Atomic done + refresh request: publish this completed frame,
                    // rather than repeating the old front and waiting another refresh.
                    front_bank<=write_bank;front_valid<=1;front_crc<=engine_crc;front_id<=engine_id;
                    display_base<=result_base;display_crc<=engine_crc;display_id<=engine_id;
                    front_param_id<=frame_param_id;front_mode<={6'b0,frame_gamma_enable,frame_correction_enable};
                    display_param_id<=frame_param_id;display_mode<={6'b0,frame_gamma_enable,frame_correction_enable};
                    write_bank<=!write_bank;pending<=0;
                end else begin
                    display_base<=front_bank ? 3*BANK_STRIDE:2*BANK_STRIDE;display_crc<=front_crc;display_id<=front_id;
                    display_param_id<=front_param_id;display_mode<=front_mode;
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
