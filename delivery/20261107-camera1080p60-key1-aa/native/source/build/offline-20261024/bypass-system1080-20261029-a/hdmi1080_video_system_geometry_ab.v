`timescale 1ns/1ps
// Independent board-system datapath. The external port is the real Pango DDR
// UI contract (4B address units, no B channel), not a private frame memory.
// Successful pixel consumption AND reader CRC AND actual FIFO drain release
// a display bank. A bad lease is quarantined until coordinated global reset.
module hdmi1080_video_system_geometry_ab #(
    parameter WIDTH=1920,HEIGHT=1080,BANK_STRIDE=1048576,MAX_RADIUS_Q22=8388608,STATS_ENABLE=0,STATS_CORE_HZ=125000000,RASTER_DOUBLE_BUFFER=0,
    HT=2200,VT=1125,HS=44,VS=5,X0=192,Y0=41,CACHE_PROFILE=0,HDMI_FISHEYE_PROFILE=0,TILE8_GROUP_WIDTH=16,RATIONAL_BROWN_PROFILE=0,MACRO_TILE_HEIGHT=8,CACHE_INDEX_BITS=6,PREFETCH_QUERY_DEPTH=0,PREFETCH_LOOKAHEAD=256,CACHE_ROW_STRIDE=0,CACHE_HEAD_PREDECODE=1,CRC_FOLD_BITS=1,READ_REQUEST_LOOKAHEAD=0,RESULT_BANKS=2,CORE_PRIORITY=0,ENABLE_RUNTIME_ROTATION=0,STARTUP_SCAN_ALIGN=0,STARTUP_SCAN_GUARD_CYCLES=0,STARTUP_PRIME_NEXT_SOURCE=0
)(
    input core_clk,pix_in_clk,pix_out_clk,rst_n,
    input telemetry_clk,telemetry_rx,output telemetry_tx,
    input [31:0] telemetry_param_id,
    input gamma_enable,correction_enable,
    input signed [23:0] cfg_rot_cx,cfg_rot_cy,
    input signed [31:0] cfg_rot_cos,cfg_rot_sin,
    input capture_admit,scan_enable,external_fault,input [7:0] external_fault_code,
    input pix_in_vsync_active,pix_in_de,input [23:0] pix_in_rgb,
    input signed [23:0] cfg_out_cx,cfg_out_cy,cfg_src_cx,cfg_src_cy,cfg_src_fx,cfg_src_fy,
    input signed [31:0] cfg_inv_fx,cfg_inv_fy,cfg_k1,cfg_k2,cfg_k3,cfg_p1,cfg_p2,
    output [27:0] awaddr,araddr,output [3:0] awlen,arlen,
    output awvalid,arvalid,input awready,arready,
    output [255:0] wdata,output [31:0] wstrb,input wready,wlast,
    input [255:0] rdata,input rvalid,rlast,input [3:0] rid,
    output pix_hs,pix_vs,pix_de,output [23:0] pix_rgb,output display_valid,
    output failed,output [7:0] fault,
    output [31:0] captured_frames,processed_frames,
    output reg [31:0] presented_frames,scan_good_frames,scan_repeat_frames,scan_blank_frames,
    output [31:0] underflows,mismatches,
    output reg source_commit,output reg [31:0] source_commit_id,output reg source_commit_bank,
    output reg [31:0] source_crc,source_pixels,
    output source_release,output [31:0] source_release_id,output released_bank,
    output result_publish,output [31:0] publish_id,output [1:0] publish_bank,
    output [31:0] last_process_cycles,
    output [31:0] pix_frame_id,output pix_frame_bank,pix_frame_start,pix_frame_last,pix_pixel_valid,
    output pix_done_toggle,pix_done_good,output [31:0] pix_done_crc,
    output processing,pending,display_active,write_bank,front_bank,
    output [1:0] capture_reserved,output [9:0] fifo_used,fifo_available,
    output reg [31:0] peak_fifo_used,
    output [31:0] cache_hits,cache_misses,queries,output read_busy,write_busy
);
    localparam FRAME_BEATS=WIDTH*HEIGHT/16;
    (* async_reg="true" *) reg [1:0] core_reset_sync=0;
    always @(posedge core_clk or negedge rst_n)
        if(!rst_n)core_reset_sync<=0;else core_reset_sync<={core_reset_sync[0],1'b1};
    // DERIVED reset candidate: synchronous-reset core-only children consume
    // the existing local release. Multiclock input/FIFO/scan retain the COMMON
    // raw reset and their own domain release. No runtime fault resets an epoch.
    wire cr=core_reset_sync[1];
    wire bank_failed,input_failed,reader_failed,read_failed,scan_failed;
    wire [7:0] bank_fault,input_fault,reader_fault,read_fault,scan_fault;
    reg controller_failed;reg [7:0] controller_fault;
    reg system_failed;reg [7:0] system_fault;
    (* async_reg="true" *) reg [1:0] scan_failed_sync=0;
    assign failed=system_failed || controller_failed || bank_failed || input_failed || reader_failed || read_failed || scan_failed_sync[1] || external_fault;
    wire stop_admit=controller_failed || system_failed || bank_failed || reader_failed || read_failed || scan_failed_sync[1] || external_fault;
    wire [7:0] upstream_fault=system_failed ? system_fault:controller_failed ? controller_fault:
        external_fault ? external_fault_code:bank_failed ? bank_fault:reader_failed ? reader_fault:
        read_failed ? read_fault:scan_failed_sync[1] ? 8'hA0:0;
    // Do not feed input_link.fault back to its core_fault input: stopping that
    // producer also raises its failed output, so that would create a loop.
    assign fault=stop_admit ? upstream_fault:input_failed ? input_fault:0;

    wire src_valid,src_ready,src_bank;wire [31:0] src_id,src_crc,src_pixels;
    wire [1:0] source_writable;
    wire [27:0] sample_ar,result_aw;wire [3:0] sample_len,result_awlen;
    wire sample_valid,sample_ready,result_awvalid,result_awready,result_wready,result_wlast;
    wire [255:0] sample_data,result_wdata;wire [31:0] result_wstrb;
    wire sample_rvalid,sample_rlast;wire [3:0] sample_rid;
    wire display_req_ready,display_grant_valid;reg display_req_valid,display_grant_ready;
    wire [27:0] display_base;wire [31:0] display_crc,display_id;
    wire [31:0] display_param_id;wire [7:0] display_mode;
    wire stats_last_valid,stats_request_valid,stats_request_ready,stats_response_valid,stats_response_ready;
    wire [31:0] stats_last_id,stats_last_param_id,stats_last_mode,stats_ticket,stats_nonce;
    wire [639:0] stats_response_body;
    reg display_done_valid,display_done_bank;
    reg [31:0] active_process_id;reg accepted_result_bank;
    assign source_release_id=active_process_id;
    assign result_publish=source_release;
    assign publish_id=active_process_id;
    assign publish_bank={1'b1,accepted_result_bank};
    wire rotation_config_valid,rotation_config_ready;wire [127:0] rotation_config_data;
    wire [31:0] selected_rotation_param_id;wire signed [31:0] selected_rotation_cos,selected_rotation_sin;
    generate if(ENABLE_RUNTIME_ROTATION)begin: runtime_rotation
        frame_rotation_config config_state(
            .ctrl_clk(telemetry_clk),.core_clk(core_clk),.rst_n(rst_n),
            .config_valid(rotation_config_valid),.config_ready(rotation_config_ready),.config_data(rotation_config_data),
            .default_param_id(telemetry_param_id),.default_cos(cfg_rot_cos),.default_sin(cfg_rot_sin),
            .frame_accept(src_valid && src_ready),.source_frame_id(src_id),
            .selected_param_id(selected_rotation_param_id),.selected_phase(),
            .selected_cos(selected_rotation_cos),.selected_sin(selected_rotation_sin),
            .applied_pulse(),.applied_source_id(),.applied_param_id());
    end else begin: original_rotation
        assign rotation_config_ready=1'b0;
        assign selected_rotation_param_id=telemetry_param_id;
        assign selected_rotation_cos=cfg_rot_cos;assign selected_rotation_sin=cfg_rot_sin;
    end endgenerate
    lens1080_bank_core_geometry_bypass #(.RATIONAL_BROWN_PROFILE(RATIONAL_BROWN_PROFILE),.MACRO_TILE_HEIGHT(MACRO_TILE_HEIGHT),.CACHE_INDEX_BITS(CACHE_INDEX_BITS),.PREFETCH_QUERY_DEPTH(PREFETCH_QUERY_DEPTH),.PREFETCH_LOOKAHEAD(PREFETCH_LOOKAHEAD),.CACHE_ROW_STRIDE(CACHE_ROW_STRIDE),.CACHE_HEAD_PREDECODE(CACHE_HEAD_PREDECODE),.CRC_FOLD_BITS(CRC_FOLD_BITS),.READ_REQUEST_LOOKAHEAD(READ_REQUEST_LOOKAHEAD),.RESULT_BANKS(RESULT_BANKS),.HDMI_FISHEYE_PROFILE(HDMI_FISHEYE_PROFILE),.CACHE_PROFILE(CACHE_PROFILE),.TILE8_GROUP_WIDTH(TILE8_GROUP_WIDTH),.WIDTH(WIDTH),.HEIGHT(HEIGHT),.BANK_STRIDE(BANK_STRIDE),.MAX_RADIUS_Q22(MAX_RADIUS_Q22),.STATS_ENABLE(STATS_ENABLE),.RASTER_DOUBLE_BUFFER(RASTER_DOUBLE_BUFFER)) bank_core(
        .gamma_enable(gamma_enable),.correction_enable(correction_enable),.cfg_rot_cx(cfg_rot_cx),.cfg_rot_cy(cfg_rot_cy),.cfg_rot_cos(selected_rotation_cos),.cfg_rot_sin(selected_rotation_sin),
        .clk(core_clk),.rst_n(cr),.source_valid(src_valid),.source_ready(src_ready),.source_bank(src_bank),.source_id(src_id),
        .source_writable(source_writable),.source_released(source_release),.released_bank(released_bank),
        .display_request_valid(display_req_valid),.display_request_ready(display_req_ready),
        .display_grant_valid(display_grant_valid),.display_grant_ready(display_grant_ready),
        .display_base(display_base),.display_crc(display_crc),.display_id(display_id),
        .telemetry_param_id(selected_rotation_param_id),.display_param_id(display_param_id),.display_mode(display_mode),
        // Recheck on the bank's actual consumption edge. A fault arriving
        // after this controller registered the release pulse must quarantine
        // the bank rather than consume a previously healthy release.
        .display_done_valid(display_done_valid && !failed),.display_done_bank(display_done_bank),
        .cfg_out_cx(cfg_out_cx),.cfg_out_cy(cfg_out_cy),.cfg_src_cx(cfg_src_cx),.cfg_src_cy(cfg_src_cy),
        .cfg_src_fx(cfg_src_fx),.cfg_src_fy(cfg_src_fy),.cfg_inv_fx(cfg_inv_fx),.cfg_inv_fy(cfg_inv_fy),
        .cfg_k1(cfg_k1),.cfg_k2(cfg_k2),.cfg_k3(cfg_k3),.cfg_p1(cfg_p1),.cfg_p2(cfg_p2),
        .araddr(sample_ar),.arlen(sample_len),.arvalid(sample_valid),.arready(sample_ready),
        .rdata(sample_data),.rvalid(sample_rvalid),.rlast(sample_rlast),.rid(sample_rid),
        .awaddr(result_aw),.awlen(result_awlen),.awvalid(result_awvalid),.awready(result_awready),
        .wdata(result_wdata),.wstrb(result_wstrb),.wready(result_wready),.wlast(result_wlast),
        .processing(processing),.pending(pending),.display_active(display_active),.write_bank(write_bank),.front_bank(front_bank),
        .completed_frames(processed_frames),.last_cycles(last_process_cycles),.hits(cache_hits),.misses(cache_misses),.queries(queries),
        .stats_last_valid(stats_last_valid),.stats_last_id(stats_last_id),.stats_last_param_id(stats_last_param_id),.stats_last_mode(stats_last_mode),
        .failed(bank_failed),.fault(bank_fault));
    wire [31:0] unused_capture_bursts,unused_result_bursts,dropped_frames,overflow_frames,no_free_frames;
    wire [7:0] last_drop_fault;
    hdmi1080_input_write_link #(.WIDTH(WIDTH),.HEIGHT(HEIGHT),.BANK_STRIDE(BANK_STRIDE),.FIFO_ADDR_BITS(6)) input_link(
        .pix_clk(pix_in_clk),.sys_clk(core_clk),.rst_n(rst_n),.enable(capture_admit && !stop_admit),
        .pix_vsync_active(pix_in_vsync_active),.pix_de(pix_in_de),.pix_rgb(pix_in_rgb),
        .core_source_writable(source_writable),.core_source_released(source_release),.core_released_bank(released_bank),
        .core_source_valid(src_valid),.core_source_ready(src_ready),.core_source_bank(src_bank),.core_source_id(src_id),
        .source_crc(src_crc),.source_pixels(src_pixels),.capture_reserved(capture_reserved),
        .core_failed(stop_admit),.core_fault(upstream_fault),
        .core_awaddr(result_aw),.core_awlen(result_awlen),.core_awvalid(result_awvalid),.core_awready(result_awready),
        .core_wdata(result_wdata),.core_wstrb(result_wstrb),.core_wready(result_wready),.core_wlast(result_wlast),
        .awaddr(awaddr),.awlen(awlen),.awvalid(awvalid),.awready(awready),.wdata(wdata),.wstrb(wstrb),.wready(wready),.wlast(wlast),
        .failed(input_failed),.fault(input_fault),.write_busy(write_busy),.capture_bursts(unused_capture_bursts),.result_bursts(unused_result_bursts),
        .accepted_frames(captured_frames),.dropped_frames(dropped_frames),.overflow_frames(overflow_frames),
        .no_free_frames(no_free_frames),.last_drop_fault(last_drop_fault));

    reg reader_start;reg [27:0] reader_base;reg [31:0] reader_expected;
    wire reader_idle,reader_done;wire [31:0] reader_beats,reader_checksum,read_frames;
    wire [27:0] display_ar;wire [3:0] display_len;wire display_arvalid,display_arready;
    wire [255:0] display_rdata,display_fifo_write_data,display_fifo_read_data;
    wire display_rvalid,display_rlast;wire [3:0] display_rid;
    wire display_fifo_push,display_fifo_pop,display_fifo_write_ready,display_fifo_read_ready,display_fifo_read_valid,display_fifo_empty;
    ddr_video_reader_crc5_local #(.FRAME_BEATS(FRAME_BEATS)) reader(
        .clk(core_clk),.rst_n(cr),.start(reader_start),.base_address(reader_base),.expected_checksum(reader_expected),
        .fifo_used(fifo_used),.fifo_ready(display_fifo_write_ready),.fifo_wr_en(display_fifo_push),.fifo_data(display_fifo_write_data),
        .araddr(display_ar),.arlen(display_len),.arvalid(display_arvalid),.arready(display_arready),
        .rdata(display_rdata),.rvalid(display_rvalid),.rlast(display_rlast),.rid(display_rid),
        .idle(reader_idle),.done(reader_done),.failed(reader_failed),.fault(reader_fault),
        .read_beats(reader_beats),.last_checksum(reader_checksum),.completed_frames(read_frames));
    video_display_async_fifo #(.DATA_BITS(256),.ADDR_BITS(9)) display_fifo(
        .wr_clk(core_clk),.rd_clk(pix_out_clk),.rst_n(rst_n),
        .wr_en(display_fifo_push),.wr_data(display_fifo_write_data),.wr_full(),.wr_ready(display_fifo_write_ready),.wr_used(fifo_used),
        .rd_en(display_fifo_pop),.rd_data(display_fifo_read_data),.rd_valid(display_fifo_read_valid),
        .rd_empty(display_fifo_empty),.rd_ready(display_fifo_read_ready),.rd_available(fifo_available));
    wire [31:0] display_read_bursts,sample_read_bursts;
    ddr_read_arbiter #(.CORE_PRIORITY(CORE_PRIORITY)) read_bus(
        .clk(core_clk),.rst_n(cr),.display_urgent(fifo_used<64),
        .c0_araddr(display_ar),.c0_arlen(display_len),.c0_arvalid(display_arvalid),.c0_arready(display_arready),
        .c0_rdata(display_rdata),.c0_rvalid(display_rvalid),.c0_rlast(display_rlast),.c0_rid(display_rid),
        .c1_araddr(sample_ar),.c1_arlen(sample_len),.c1_arvalid(sample_valid),.c1_arready(sample_ready),
        .c1_rdata(sample_data),.c1_rvalid(sample_rvalid),.c1_rlast(sample_rlast),.c1_rid(sample_rid),
        .araddr(araddr),.arlen(arlen),.arvalid(arvalid),.arready(arready),.rdata(rdata),.rvalid(rvalid),.rlast(rlast),.rid(rid),
        .failed(read_failed),.fault(read_fault),.busy(read_busy),.bursts0(display_read_bursts),.bursts1(sample_read_bursts));

    wire scan_request_toggle,scan_grant_ack;wire [31:0] scan_request_epoch;
    reg grant_toggle,grant_valid;reg [31:0] grant_epoch,grant_checksum,grant_id;reg grant_bank;
    reg done_ack_toggle;
    reg [31:0] grant_param_id;reg [7:0] grant_mode;
    wire [15:0] scan_pixel_x,scan_pixel_y;
    wire [31:0] scan_active_epoch,scan_active_param_id;
    wire [7:0] scan_active_mode;wire scan_metadata_valid;
    wire [31:0] scan_done_epoch,scan_done_id;wire scan_done_bank;
    wire [31:0] consumed_pixels,scan_completed_frames;
    wire scan_draining,scan_active;
    // Opt-in startup phase selection only. Core, capture, DDR and all FIFO resets
    // remain independent of this permit. The completed pending result is already
    // validated by bank_core; no source/result lease is released here.
    // Opt-in continuous-stream priming. Input link already qualifies complete
    // descriptors. Wait for the NEXT held complete source, not an elapsed time.
    // Does not gate capture/core/FIFO reset or change the running raster.
    wire startup_prime_ready=(STARTUP_PRIME_NEXT_SOURCE==0) ||
        (src_valid && src_pixels==WIDTH*HEIGHT && src_id!=source_commit_id);
    wire startup_scan_permit;
    generate if(STARTUP_SCAN_ALIGN!=0)begin: one_shot_scan_align
        reg first_result_ready;
        localparam GUARD_COUNT_BITS=STARTUP_SCAN_GUARD_CYCLES>0 ?
            $clog2(STARTUP_SCAN_GUARD_CYCLES+1):1;
        reg [GUARD_COUNT_BITS-1:0] startup_guard_count;
        initial if(STARTUP_SCAN_GUARD_CYCLES<0)
            $fatal(1,"STARTUP_SCAN_GUARD_CYCLES must be nonnegative");
        always @(posedge core_clk)begin
            if(!cr)begin first_result_ready<=0;startup_guard_count<=0;end
            else if(!first_result_ready)begin
                if(!pending || failed || !startup_prime_ready)startup_guard_count<=0;
                else if(STARTUP_SCAN_GUARD_CYCLES==0)
                    first_result_ready<=1;
                else if(startup_guard_count==STARTUP_SCAN_GUARD_CYCLES)
                    first_result_ready<=1;
                else startup_guard_count<=startup_guard_count+1'b1;
            end
        end
        // Monotonic until common reset. Runtime disable/fault never restarts phase.
        assign startup_scan_permit=first_result_ready;
    end else begin: original_scan_phase
        assign startup_scan_permit=1'b1;
    end endgenerate
    (* async_reg="true" *) reg [1:0] scan_enable_sync=0,scan_abort_sync=0;
    always @(posedge pix_out_clk or negedge rst_n)
        if(!rst_n)begin scan_enable_sync<=0;scan_abort_sync<=0;end
        else begin scan_enable_sync<={scan_enable_sync[0],scan_enable && startup_scan_permit};scan_abort_sync<={scan_abort_sync[0],system_failed};end
    ddr_video_output_1080_board_final_publish_local #(.STARTUP_SCAN_ALIGN(STARTUP_SCAN_ALIGN),.WIDTH(WIDTH),.HEIGHT(HEIGHT),.HT(HT),.VT(VT),.HS(HS),.VS(VS),.X0(X0),.Y0(Y0),.AW(WIDTH),.AH(HEIGHT)) output_video(
        .clk(pix_out_clk),.rst_n(rst_n),.enable(scan_enable_sync[1]),.abort(scan_abort_sync[1]),.abort_fault(system_fault),
        .request_toggle(scan_request_toggle),.request_epoch(scan_request_epoch),
        .grant_toggle(grant_toggle),.grant_valid(grant_valid),.grant_epoch(grant_epoch),
        .grant_checksum(grant_checksum),.grant_id(grant_id),.grant_bank(grant_bank),.grant_ack_toggle(scan_grant_ack),
        .grant_param_id(grant_param_id),.grant_mode(grant_mode),
        .fifo_ready(display_fifo_read_ready),.fifo_valid(display_fifo_read_valid),.fifo_data(display_fifo_read_data),.fifo_rd_en(display_fifo_pop),
        .hs(pix_hs),.vs(pix_vs),.de(pix_de),.r(pix_rgb[23:16]),.g(pix_rgb[15:8]),.b(pix_rgb[7:0]),.display_valid(display_valid),
        .done_toggle(pix_done_toggle),.done_ack_toggle(done_ack_toggle),.done_good(pix_done_good),
        .done_epoch(scan_done_epoch),.done_id(scan_done_id),.done_bank(scan_done_bank),.done_crc(pix_done_crc),.consumed_pixels(consumed_pixels),
        .frame_active(scan_active),.active_id(pix_frame_id),.active_bank(pix_frame_bank),
        .frame_start(pix_frame_start),.frame_last(pix_frame_last),.pixel_valid(pix_pixel_valid),
        .pixel_x(scan_pixel_x),.pixel_y(scan_pixel_y),.active_epoch(scan_active_epoch),
        .active_param_id(scan_active_param_id),.active_mode(scan_active_mode),.metadata_valid(scan_metadata_valid),
        .failed(scan_failed),.fault(scan_fault),.draining(scan_draining),
        .completed_frames(scan_completed_frames),.underflows(underflows),.mismatches(mismatches));

    (* async_reg="true" *) reg [1:0] request_sync=0,grant_ack_sync=0,done_sync=0;
    reg request_seen,done_seen,response_busy,awaiting_bank_grant;
    reg [31:0] request_epoch_hold;
    reg lease_active,lease_bank,reader_finished,pixel_finished;
    reg [31:0] lease_id,lease_crc,lease_epoch,last_presented_id;
    reg [31:0] pixel_done_id,pixel_done_crc,pixel_done_epoch,pixel_done_count;
    reg pixel_done_bank,pixel_done_good;
    always @(posedge core_clk)begin
        if(!cr)begin
            scan_failed_sync<=0;request_sync<=0;grant_ack_sync<=0;done_sync<=0;
            system_failed<=0;system_fault<=0;controller_failed<=0;controller_fault<=0;
            source_commit<=0;source_commit_id<=0;source_commit_bank<=0;source_crc<=0;source_pixels<=0;active_process_id<=0;accepted_result_bank<=0;
            presented_frames<=0;scan_good_frames<=0;scan_repeat_frames<=0;scan_blank_frames<=0;last_presented_id<=0;peak_fifo_used<=0;
            request_seen<=0;done_seen<=0;response_busy<=0;awaiting_bank_grant<=0;request_epoch_hold<=0;
            display_req_valid<=0;display_grant_ready<=0;display_done_valid<=0;display_done_bank<=0;
            reader_start<=0;reader_base<=0;reader_expected<=0;reader_finished<=0;pixel_finished<=0;
            grant_toggle<=0;grant_valid<=0;grant_epoch<=0;grant_checksum<=0;grant_id<=0;grant_bank<=0;done_ack_toggle<=0;
            grant_param_id<=0;grant_mode<=0;
            lease_active<=0;lease_bank<=0;lease_id<=0;lease_crc<=0;lease_epoch<=0;
            pixel_done_id<=0;pixel_done_crc<=0;pixel_done_epoch<=0;pixel_done_count<=0;pixel_done_bank<=0;pixel_done_good<=0;
        end else begin
            scan_failed_sync<={scan_failed_sync[0],scan_failed};
            request_sync<={request_sync[0],scan_request_toggle};grant_ack_sync<={grant_ack_sync[0],scan_grant_ack};done_sync<={done_sync[0],pix_done_toggle};
            reader_start<=0;display_grant_ready<=0;display_done_valid<=0;source_commit<=0;
            if(fifo_used>peak_fifo_used)peak_fifo_used<=fifo_used;
            if(src_valid && src_ready)begin
                source_commit<=1;source_commit_id<=src_id;source_commit_bank<=src_bank;source_crc<=src_crc;source_pixels<=src_pixels;active_process_id<=src_id;accepted_result_bank<=write_bank;
            end
            if(failed && !system_failed)begin system_failed<=1;system_fault<=fault;end
            if(response_busy && grant_ack_sync[1]==grant_toggle)response_busy<=0;
            if(request_sync[1]!=request_seen)begin
                request_seen<=request_sync[1];request_epoch_hold<=scan_request_epoch;
                if(response_busy || awaiting_bank_grant || display_req_valid || lease_active)begin
                    controller_failed<=1;controller_fault<=8'hB1;
                end else if(!failed && scan_enable && display_req_ready && reader_idle && fifo_used==0)begin
                    display_req_valid<=1;
                end else begin
                    // No ready front at THIS refresh boundary: promptly return
                    // a blank grant, never a late mid-picture lease.
                    grant_valid<=0;grant_epoch<=scan_request_epoch;grant_checksum<=0;grant_id<=0;grant_bank<=0;
                    grant_param_id<=0;grant_mode<=0;
                    grant_toggle<=!grant_toggle;response_busy<=1;scan_blank_frames<=scan_blank_frames+1'b1;
                end
            end
            if(display_req_valid && display_req_ready)begin display_req_valid<=0;awaiting_bank_grant<=1;end
            if(awaiting_bank_grant && display_grant_valid && !response_busy && !failed)begin
                display_grant_ready<=1;awaiting_bank_grant<=0;
                lease_active<=1;lease_bank<=display_base/BANK_STRIDE-2;lease_id<=display_id;lease_crc<=display_crc;lease_epoch<=request_epoch_hold;
                reader_base<=display_base;reader_expected<=display_crc;reader_start<=1;reader_finished<=0;pixel_finished<=0;
                grant_valid<=1;grant_epoch<=request_epoch_hold;grant_checksum<=display_crc;grant_id<=display_id;grant_bank<=display_base/BANK_STRIDE-2;
                grant_param_id<=display_param_id;grant_mode<=display_mode;
                grant_toggle<=!grant_toggle;response_busy<=1;
            end
            if(reader_done)begin
                reader_finished<=1;
                if(!lease_active || reader_beats!=FRAME_BEATS || reader_checksum!=lease_crc)begin controller_failed<=1;controller_fault<=8'hB2;end
            end
            if(done_sync[1]!=done_seen)begin
                done_seen<=done_sync[1];done_ack_toggle<=done_sync[1];
                pixel_done_id<=scan_done_id;pixel_done_bank<=scan_done_bank;pixel_done_epoch<=scan_done_epoch;
                pixel_done_crc<=pix_done_crc;pixel_done_count<=consumed_pixels;pixel_done_good<=pix_done_good;pixel_finished<=1;
                if(!lease_active || scan_done_id!=lease_id || scan_done_bank!=lease_bank || scan_done_epoch!=lease_epoch ||
                   !pix_done_good || pix_done_crc!=lease_crc || consumed_pixels!=WIDTH*HEIGHT)begin
                    controller_failed<=1;controller_fault<=8'hB3;
                end
            end
            if(lease_active && reader_finished && pixel_finished && reader_idle && fifo_used==0 && !failed)begin
                if(!pixel_done_good || pixel_done_id!=lease_id || pixel_done_bank!=lease_bank || pixel_done_epoch!=lease_epoch ||
                    pixel_done_crc!=lease_crc || pixel_done_count!=WIDTH*HEIGHT)begin controller_failed<=1;controller_fault<=8'hB4;end
                else begin
                    display_done_valid<=1;display_done_bank<=lease_bank;lease_active<=0;pixel_finished<=0;reader_finished<=0;
                    scan_good_frames<=scan_good_frames+1'b1;
                    if(lease_id>last_presented_id)begin presented_frames<=presented_frames+1'b1;last_presented_id<=lease_id;end
                    else if(lease_id==last_presented_id)scan_repeat_frames<=scan_repeat_frames+1'b1;
                    else begin controller_failed<=1;controller_fault<=8'hB5;end
                end
            end
        end
    end
    // Passive b4 link. No telemetry ready/fault/reset output feeds the video path.
    // Tags are held with the same grant until the existing grant acknowledgement.
    generate if(STATS_ENABLE)begin: measurement_enabled
        core_stats_snapshot #(.CORE_HZ(STATS_CORE_HZ),.LIGHT(1),.FAULT_DETAIL_ENABLE(1)) statistics(
            .clk(core_clk),.rst_n(cr),.request_valid(stats_request_valid),.request_ready(stats_request_ready),
            .ticket(stats_ticket),.nonce(stats_nonce),.response_valid(stats_response_valid),
            .response_ready(stats_response_ready),.response_body(stats_response_body),
            .last_valid(stats_last_valid),.last_cycles(last_process_cycles),.last_id(stats_last_id),
            .last_param_id(stats_last_param_id),.last_mode(stats_last_mode),
            .captured(captured_frames),.processed(processed_frames),.presented(presented_frames),
            .scan_good(scan_good_frames),.scan_repeat(scan_repeat_frames),.scan_blank(scan_blank_frames),
            .dropped(dropped_frames),.overflow(overflow_frames),.no_free(no_free_frames),
            .last_presented_id(last_presented_id),.last_drop_fault(last_drop_fault),
            .source_stalled(src_valid && !src_ready),.processing(processing),.pending(pending),.display_lease(lease_active),
            .read_busy(read_busy),.write_busy(write_busy),.snapshot_busy(1'b0),.failed(failed),
            .fault_detail({controller_fault,input_fault,fault}));
    end else begin: measurement_disabled
        assign stats_request_ready=0;assign stats_response_valid=0;assign stats_response_body=0;
    end endgenerate
    telemetry_uart_link #(.WIDTH(WIDTH),.HEIGHT(HEIGHT),.CLOCK_HZ(27000000),.BAUD(115200),.STATS_ENABLE(STATS_ENABLE),.STATS_LIGHT(1),.ENABLE_RUNTIME_ROTATION(ENABLE_RUNTIME_ROTATION)) telemetry (
        .ctrl_clk(telemetry_clk),.pix_clk(pix_out_clk),.rst_n(rst_n),
        .snapshot_core_clk(core_clk),.stats_request_valid(stats_request_valid),.stats_request_ready(stats_request_ready),
        .stats_ticket(stats_ticket),.stats_nonce(stats_nonce),.stats_response_valid(stats_response_valid),
        .stats_response_ready(stats_response_ready),.stats_response_body(stats_response_body),
        .snapshot_request_ready(1'b0),.snapshot_stop_ready(1'b0),.snapshot_ack_valid(1'b0),.snapshot_ack_body(352'd0),
        .snapshot_byte_valid(1'b0),.snapshot_byte_data(8'd0),.snapshot_release_valid(1'b0),
        .uart_rx(telemetry_rx),.uart_tx(telemetry_tx),
        .rotation_base_param_id(telemetry_param_id),.rotation_config_valid(rotation_config_valid),
        .rotation_config_ready(rotation_config_ready),.rotation_config_data(rotation_config_data),
        .pixel_valid(pix_pixel_valid),.frame_start(pix_frame_start),.frame_last(pix_frame_last),
        .video_abort(scan_failed || scan_abort_sync[1]),
        .pixel_x(scan_pixel_x),.pixel_y(scan_pixel_y),.pixel_rgb(pix_rgb),
        .metadata_valid(scan_metadata_valid),.scan_epoch(scan_active_epoch),
        .frame_id(pix_frame_id),.bank(pix_frame_bank),.param_id(scan_active_param_id),.mode(scan_active_mode),
        .rx_queued(),.rx_rejected(),.rx_busy_drops(),.rx_timeouts(),.signature_dropped());
endmodule
