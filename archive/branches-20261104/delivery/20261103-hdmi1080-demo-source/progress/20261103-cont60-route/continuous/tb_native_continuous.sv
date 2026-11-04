`timescale 1ps/1ps
// Normalized digital input -> actual DMA -> correction -> actual async FIFO ->
// registered DE/RGB scan. Modeled DDR UI only; never a physical PHY test.
module tb_native_continuous;
    parameter CACHE_PROFILE=2,PIX_HZ=148500000,FRAMES=3,TRACE_PIXELS=0,MAX_CYCLES=80000000,CHECKER_TEST=0;
    `include "continuous_config.vh"
    localparam W=VEC_WIDTH,H=VEC_HEIGHT,N=W*H,FB=N/16,FU=N/2,STRIDE=1048576;
    localparam NATIVE=W==1920&&H==1080;
    // Three complete input rasters without ready/presented gating.
    // Native geometry has exact60Hz frame starts; pilot geometry is separately labeled.
    localparam [63:0] PERIOD_PS=(64'd2*PIXEL_HALF_NUM*SIM_HT*SIM_VT)/297;
    reg core_clk=0,pix_in_clk=0,pix_out_clk=0;
    always #4000 core_clk=~core_clk;
    integer in_phase=0,in_delay,out_phase=0,out_delay;
    initial forever begin
        in_phase=in_phase+PIXEL_HALF_NUM;in_delay=in_phase/297;in_phase=in_phase%297;
        #(in_delay)pix_in_clk=~pix_in_clk;
    end
    initial begin
        #(SIM_OUTPUT_PHASE_PS);
        forever begin
            out_phase=out_phase+PIXEL_HALF_NUM;out_delay=out_phase/297;out_phase=out_phase%297;
            #(out_delay)pix_out_clk=~pix_out_clk;
        end
    end
    reg telemetry_clk=0,telemetry_rx=1;wire telemetry_tx;
    reg [31:0] telemetry_param_id=VEC_PARAM_ID;
    always #18518.5185185 telemetry_clk=~telemetry_clk;
    localparam real UART_BIT_PS=4.0*1000000000000.0/27000000.0;
    localparam TEST_ENABLE=0;
    // Source-commit application payload; never inferred from display refresh.
    reg signed [23:0] live_out_cx=VEC_OUT_CX;
    reg signed [23:0] live_out_cy=VEC_OUT_CY;
    reg signed [23:0] live_src_cx=VEC_SRC_CX;
    reg signed [23:0] live_src_cy=VEC_SRC_CY;
    reg signed [23:0] live_src_fx=VEC_SRC_FX;
    reg signed [23:0] live_src_fy=VEC_SRC_FY;
    reg signed [31:0] live_inv_fx=VEC_INV_FX;
    reg signed [31:0] live_inv_fy=VEC_INV_FY;
    reg signed [31:0] live_k1=VEC_K1;
    reg signed [31:0] live_k2=VEC_K2;
    reg signed [31:0] live_k3=VEC_K3;
    reg signed [31:0] live_p1=VEC_P1;
    reg signed [31:0] live_p2=VEC_P2;
    reg gamma_enable=0,correction_enable=1;
    reg signed [23:0] rot_cx=VEC_ROT_CX,rot_cy=VEC_ROT_CY;
    reg signed [31:0] rot_cos=VEC_ROT_COS,rot_sin=VEC_ROT_SIN;
    reg rst_n=0,capture_admit=0,scan_enable=0,external_fault=0;
    reg [7:0] external_fault_code=0;
    reg pix_in_vsync_active=0,pix_in_de=0;reg [23:0] pix_in_rgb=0;
    wire pix_hs,pix_vs,pix_de,display_valid,failed;wire [23:0] pix_rgb;wire [7:0] fault;
    wire [31:0] captured_frames,processed_frames,presented_frames,scan_good_frames,scan_repeat_frames,scan_blank_frames,underflows,mismatches;
    wire source_commit,source_commit_bank,source_release,released_bank,result_publish;
    wire [31:0] source_commit_id,source_crc,source_pixels,source_release_id,publish_id,last_process_cycles;
    wire [1:0] publish_bank;
    wire [31:0] pix_frame_id,pix_done_crc;wire pix_frame_bank,pix_frame_start,pix_frame_last,pix_pixel_valid,pix_done_toggle,pix_done_good;
    wire processing,pending,display_active,write_bank,front_bank,read_busy,write_busy;
    wire [1:0] capture_reserved;wire [9:0] fifo_used,fifo_available;
    wire [31:0] peak_fifo_used,cache_hits,cache_misses,queries;
    wire [27:0] araddr,awaddr;wire [3:0] arlen,awlen;wire arvalid,awvalid;
    reg arready=0,awready=0,wready=0,wlast=0,rvalid=0,rlast=0;
    reg [255:0] rdata=0;reg [3:0] rid=0;wire [255:0] wdata;wire [31:0] wstrb;
    hdmi1080_video_system_geometry_ab #(.CACHE_PROFILE(CACHE_PROFILE),.RASTER_DOUBLE_BUFFER(1),.STATS_ENABLE(1),.WIDTH(W),.HEIGHT(H),.BANK_STRIDE(STRIDE),.MAX_RADIUS_Q22(VEC_RADIUS_GUARD_Q22),
        .HT(SIM_HT),.VT(SIM_VT),.HS(SIM_HS),.VS(SIM_VS),.X0(SIM_X0),.Y0(SIM_Y0)
    ) dut(
        .core_clk(core_clk),.pix_in_clk(pix_in_clk),.pix_out_clk(pix_out_clk),.rst_n(rst_n),
        .telemetry_clk(telemetry_clk),.telemetry_rx(telemetry_rx),.telemetry_tx(telemetry_tx),.telemetry_param_id(telemetry_param_id),
        .gamma_enable(gamma_enable),.correction_enable(correction_enable),.cfg_rot_cx(rot_cx),.cfg_rot_cy(rot_cy),.cfg_rot_cos(rot_cos),.cfg_rot_sin(rot_sin),
        .capture_admit(capture_admit),.scan_enable(scan_enable),.external_fault(external_fault),.external_fault_code(external_fault_code),
        .pix_in_vsync_active(pix_in_vsync_active),.pix_in_de(pix_in_de),.pix_in_rgb(pix_in_rgb),
        .cfg_out_cx(live_out_cx),.cfg_out_cy(live_out_cy),.cfg_src_cx(live_src_cx),.cfg_src_cy(live_src_cy),
        .cfg_src_fx(live_src_fx),.cfg_src_fy(live_src_fy),.cfg_inv_fx(live_inv_fx),.cfg_inv_fy(live_inv_fy),
        .cfg_k1(live_k1),.cfg_k2(live_k2),.cfg_k3(live_k3),.cfg_p1(live_p1),.cfg_p2(live_p2),
        .awaddr(awaddr),.awlen(awlen),.awvalid(awvalid),.awready(awready),.wdata(wdata),.wstrb(wstrb),.wready(wready),.wlast(wlast),
        .araddr(araddr),.arlen(arlen),.arvalid(arvalid),.arready(arready),.rdata(rdata),.rvalid(rvalid),.rlast(rlast),.rid(rid),
        .pix_hs(pix_hs),.pix_vs(pix_vs),.pix_de(pix_de),.pix_rgb(pix_rgb),.display_valid(display_valid),.failed(failed),.fault(fault),
        .captured_frames(captured_frames),.processed_frames(processed_frames),.presented_frames(presented_frames),
        .scan_good_frames(scan_good_frames),.scan_repeat_frames(scan_repeat_frames),.scan_blank_frames(scan_blank_frames),
        .underflows(underflows),.mismatches(mismatches),.source_commit(source_commit),.source_commit_id(source_commit_id),
        .source_commit_bank(source_commit_bank),.source_crc(source_crc),.source_pixels(source_pixels),
        .source_release(source_release),.source_release_id(source_release_id),.released_bank(released_bank),
        .result_publish(result_publish),.publish_id(publish_id),.publish_bank(publish_bank),.last_process_cycles(last_process_cycles),
        .pix_frame_id(pix_frame_id),.pix_frame_bank(pix_frame_bank),.pix_frame_start(pix_frame_start),.pix_frame_last(pix_frame_last),
        .pix_pixel_valid(pix_pixel_valid),.pix_done_toggle(pix_done_toggle),.pix_done_good(pix_done_good),.pix_done_crc(pix_done_crc),
        .processing(processing),.pending(pending),.display_active(display_active),.write_bank(write_bank),.front_bank(front_bank),
        .capture_reserved(capture_reserved),.fifo_used(fifo_used),.fifo_available(fifo_available),.peak_fifo_used(peak_fifo_used),
        .cache_hits(cache_hits),.cache_misses(cache_misses),.queries(queries),.read_busy(read_busy),.write_busy(write_busy));

    // DDR/UI model is inherited in behavior from the accepted pure32 system:
    // one read burst, one write burst, AW/W0 same-edge support and fixed stalls.
    // No input frame is preloaded; normalized video must traverse actual DMA.
    reg [255:0] memory[0:4*FB-1];
    reg [255:0] packed_source[0:FRAMES*FB-1];
    reg [15:0] sources[0:FRAMES*N-1],goldens[0:FRAMES*N-1];
    reg [31:0] source_crcs[0:FRAMES-1],result_crcs[0:FRAMES-1];
    integer ticks=0,rleft=0,rindex=0,wleft=0,windex=0;
    integer scan_count=0,last_scan_id=0,normal_trace,perf_file;
    integer scans[0:3],i,frame,normal_done=0,commits=0,publishes=0,scan_crc_checks=0;
    reg done_seen=0;
    integer next_scan_id=1,scans_started=0,active_scan_id=0,checked_scan_id=0;
    integer crc_scan_id=0;reg scan_open=0;
    time previous_scan_first=0,last_input_start=0;
    reg drive_complete=0;
    wire [31:0] checked_source_crc=(CHECKER_TEST==2 && source_commit_id==2) ? source_crcs[2]:source_crc;

    function automatic [23:0] expand565(input [15:0] p);
        expand565={p[15:11],p[15:13],p[10:5],p[10:9],p[4:0],p[4:2]};
    endfunction
    function automatic integer location(input [27:0] address);
        integer bank,offset;
        begin
            bank=address/STRIDE;offset=(address%STRIDE)>>3;
            if(bank<0 || bank>3 || offset<0 || offset>=FB || address[2:0]!=0)
                $fatal(1,"DDR address outside four real frame banks %h",address);
            location=bank*FB+offset;
        end
    endfunction
    always @(negedge core_clk)begin
        ticks=ticks+1;
        awready=rst_n && wleft==0 && ticks%7>=2;
        wready=rst_n && (wleft!=0 || (awvalid && awready)) && ticks%5!=0;
        wlast=wleft!=0 ? wleft==1:awlen==0;
        arready=rst_n && rleft==0 && ticks%7!=0;
        rvalid=rst_n && rleft!=0 && ticks%3!=0;
        rlast=rleft==1;rid=0;
        if(rvalid)rdata=memory[rindex];
    end

    // Testbench-only profile observation. All busy windows include cache AR,
    // FILL and RAM SCATTER, excluding allocator/SELECT. No production outputs.
    wire cache_refill_busy,cache_scatter,cache_overlap_read;
    generate if(CACHE_PROFILE==2)begin: observe_runtime
        assign cache_refill_busy=dut.bank_core.engine.core.sampler.runtime_cache.cache.store_fill_busy;
        assign cache_scatter=dut.bank_core.engine.core.sampler.runtime_cache.cache.store.scatter_write;
        assign cache_overlap_read=cache_scatter && dut.bank_core.engine.core.sampler.runtime_cache.cache.store.read_fire;
    end else if(CACHE_PROFILE==1)begin: observe_scatter16
        wire [3:0] state=dut.bank_core.engine.core.sampler.serial_cache.cache.widened_fill.inner.state;
        assign cache_refill_busy=state==2 || state==3 || state==4;
        assign cache_scatter=state==4;
        assign cache_overlap_read=1'b0; // Serial FSM excludes reads while scatter.
    end else begin: observe_scatter32
        wire [3:0] state=dut.bank_core.engine.core.sampler.serial_cache.cache.original_fill.inner.state;
        assign cache_refill_busy=state==2 || state==3 || state==4;
        assign cache_scatter=state==4;
        assign cache_overlap_read=1'b0;
    end endgenerate
    integer frame_open=0,frame_id_open=0,start_tick=0,next_query_progress=65536;
    integer model_miss_match=-1,model_reference_match=-1;
    integer hits_start=0,misses_start=0,queries_start=0;
    integer frame_busy=0,frame_scatter=0,frame_overlap=0,frame_ar_wait=0,frame_ar=0,frame_rbeats=0;
    always @(posedge core_clk)begin
        if(!rst_n)begin rleft<=0;wleft<=0;rindex<=0;windex<=0;frame_open=0;end
        else begin
            if(ticks>MAX_CYCLES)$fatal(1,"bounded fullpipeline cycle watchdog profile=%0d",CACHE_PROFILE);
            if(failed)$fatal(1,"CONT_FIRST_BOTTLENECK SYSTEM_FAULT fault=%h profile=%0d input_frame=%0d core_tick=%0d",fault,CACHE_PROFILE,frame,ticks);
            if(dut.dropped_frames!=0 || dut.overflow_frames!=0 || dut.no_free_frames!=0)
                $fatal(1,"CONT_FIRST_BOTTLENECK DROP_COUNTER input_frame=%0d dropped=%0d overflow=%0d no_free=%0d core_tick=%0d",frame,dut.dropped_frames,dut.overflow_frames,dut.no_free_frames,ticks);
            if(arvalid && arready)begin rleft<=arlen+1;rindex<=location(araddr);end
            if(rvalid)begin rleft<=rleft-1;rindex<=rindex+1;end
            if(awvalid && awready)begin
                wleft<=awlen+1;windex<=location(awaddr);
                if(wready)begin
                    if(wstrb!==32'hffffffff || wlast!==(awlen==0))$fatal(1,"Bad first W beat");
                    memory[location(awaddr)]<=wdata;wleft<=awlen;windex<=location(awaddr)+1;
                end
            end else if(wready && wleft!=0)begin
                if(wstrb!==32'hffffffff || wlast!==(wleft==1))$fatal(1,"Bad W burst");
                memory[windex]<=wdata;wleft<=wleft-1;windex<=windex+1;
            end
            // Actual bank source acceptance, not the registered source_commit
            // notification pulse, starts the per-frame core measurement window.
            if(dut.src_valid && dut.src_ready)begin
                if(frame_open)$fatal(1,"overlapping process windows");
                frame_open=1;frame_id_open=dut.src_id;start_tick=ticks;next_query_progress=65536;
                $display("BEGIN_NATIVE_FULLSYSTEM_PROCESS profile=%0d frame_id=%0d core_tick=%0d",CACHE_PROFILE,dut.src_id,ticks);$fflush();
                hits_start=cache_hits;misses_start=cache_misses;queries_start=queries;
                frame_busy=0;frame_scatter=0;frame_overlap=0;frame_ar_wait=0;frame_ar=0;frame_rbeats=0;
            end
            if(frame_open)begin
                if(cache_refill_busy)frame_busy=frame_busy+1;
                if(cache_scatter)frame_scatter=frame_scatter+1;
                if(cache_overlap_read)frame_overlap=frame_overlap+1;
                if(dut.sample_valid && !dut.sample_ready)frame_ar_wait=frame_ar_wait+1;
                if(dut.sample_valid && dut.sample_ready)frame_ar=frame_ar+1;
                if(dut.sample_rvalid)frame_rbeats=frame_rbeats+1;
                if(queries-queries_start>=next_query_progress)begin
                    $display("PROGRESS_NATIVE_FULLSYSTEM stage=correction_queries frame_id=%0d queries=%0d core_tick=%0d",frame_id_open,queries-queries_start,ticks);
                    next_query_progress=next_query_progress+65536;$fflush();
                end
            end
            if(source_commit)begin
                commits=commits+1;
                if(source_commit_id!=commits || source_pixels!=N || checked_source_crc!==source_crcs[source_commit_id-1])
                    $fatal(1,"CONT_SOURCE_ID_OR_DROP checker_test=%0d ID=%0d raw_crc=%h checked_crc=%h expected_crc=%h driver_frame=%0d core_tick=%0d",CHECKER_TEST,source_commit_id,source_crc,checked_source_crc,source_crcs[commits-1],frame,ticks);
                $fdisplay(normal_trace,"C %0d %0d %08x %0d",source_commit_id,source_commit_bank,source_crc,ticks);
                $display("COMMIT_NATIVE_FULLSYSTEM frame_id=%0d pixels=%0d CRC=%08x core_tick=%0d",source_commit_id,source_pixels,source_crc,ticks);$fflush();
            end
            if(result_publish)begin
                publishes=publishes+1;
                if(!frame_open || publish_id!=frame_id_open || publish_id!=publishes ||
                    dut.bank_core.pending_crc!==result_crcs[publish_id-1] || queries-queries_start!=N ||
                    cache_misses-misses_start!=frame_ar || frame_rbeats!=8*frame_ar ||
                    frame_scatter!=(CACHE_PROFILE==1 ? 16:32)*frame_ar)
                    $fatal(1,"process identity/CRC/cache/fill counters profile=%0d ID=%0d h=%0d m=%0d q=%0d ar=%0d rbeats=%0d scatter=%0d",CACHE_PROFILE,publish_id,cache_hits-hits_start,cache_misses-misses_start,queries-queries_start,frame_ar,frame_rbeats,frame_scatter);
                model_miss_match=(cache_misses-misses_start)==MODEL_EXPECTED_MISSES;
                model_reference_match=(cache_hits-hits_start+cache_misses-misses_start)==MODEL_EXPECTED_REFS;
                if(!model_miss_match || !model_reference_match)
                    $display("NATIVE_FULLSYSTEM_MODEL_MISMATCH frame_id=%0d observed_misses=%0d model_expected_misses=%0d model_miss_match=%0d observed_refs=%0d model_expected_refs=%0d model_reference_match=%0d",publish_id,cache_misses-misses_start,MODEL_EXPECTED_MISSES,model_miss_match,cache_hits-hits_start+cache_misses-misses_start,MODEL_EXPECTED_REFS,model_reference_match);
                // legacy+1 is sourceaccept->bank-success distance. The separate
                // notification distance includes the registered release pulse.
                $fdisplay(perf_file,"%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d",CACHE_PROFILE,publish_id,last_process_cycles,last_process_cycles+1,ticks-start_tick,cache_hits-hits_start,cache_misses-misses_start,queries-queries_start,frame_busy,frame_scatter,frame_overlap,frame_ar_wait,frame_rbeats,dut.dropped_frames,scan_repeat_frames,dut.no_free_frames,MODEL_EXPECTED_MISSES,model_miss_match,cache_hits-hits_start+cache_misses-misses_start,MODEL_EXPECTED_REFS,model_reference_match);
                frame_open=0;
                $fdisplay(normal_trace,"R %0d %0d %0d",source_release_id,released_bank,ticks);
                $display("PUBLISH_NATIVE_FULLSYSTEM frame_id=%0d legacy_cycles=%0d legacy_plus1=%0d notification_edges=%0d core_tick=%0d",publish_id,last_process_cycles,last_process_cycles+1,ticks-start_tick,ticks);$fflush();
            end
        end
    end
    always @(negedge pix_out_clk)if(rst_n)begin
        if(pix_pixel_valid)begin
            if(pix_frame_start)begin
                checked_scan_id=(CHECKER_TEST==1 && scans_started==1) ? 1:pix_frame_id;
                if(scan_open || checked_scan_id!=next_scan_id)
                    $fatal(1,"CONT_REPEAT_OR_REORDER checker_test=%0d actual_id=%0d checked_id=%0d expected_id=%0d core_tick=%0d",CHECKER_TEST,pix_frame_id,checked_scan_id,next_scan_id,ticks);
                if(previous_scan_first!=0 && ($time-previous_scan_first<PERIOD_PS || $time-previous_scan_first>PERIOD_PS+1))
                    $fatal(1,"CONT_SCAN_CADENCE_GAP id=%0d gap_ps=%0t expected_floor_ps=%0d core_tick=%0d",pix_frame_id,$time-previous_scan_first,PERIOD_PS,ticks);
                previous_scan_first=$time;scan_open=1;active_scan_id=checked_scan_id;scan_count=0;scans_started=scans_started+1;
                $display("CONT_SCAN_FIRST id=%0d time_ps=%0t core_tick=%0d",active_scan_id,$time,ticks);$fflush();
            end
            if(!scan_open || pix_frame_id!=active_scan_id || active_scan_id<1 || active_scan_id>FRAMES || scan_count>=N)
                $fatal(1,"CONT_SCAN_ID_COUNT id=%0d active=%0d count=%0d core_tick=%0d",pix_frame_id,active_scan_id,scan_count,ticks);
            if(pix_rgb!==expand565(goldens[(active_scan_id-1)*N+scan_count]))
                $fatal(1,"CONT_FULLPIXEL_ORACLE id=%0d pixel=%0d actual=%h expected=%h core_tick=%0d",active_scan_id,scan_count,pix_rgb,expand565(goldens[(active_scan_id-1)*N+scan_count]),ticks);
            if(TRACE_PIXELS)$fdisplay(normal_trace,"P %0d %0d %06x",active_scan_id,scan_count,pix_rgb);
            scan_count=scan_count+1;
            if(scan_count%65536==0)begin
                $display("CONT_PROGRESS stage=scan id=%0d pixels=%0d core_tick=%0d",active_scan_id,scan_count,ticks);$fflush();
            end
            if(pix_frame_last)begin
                if(scan_count!=N)$fatal(1,"CONT_PARTIAL_SCAN id=%0d count=%0d",active_scan_id,scan_count);
                scans[active_scan_id]=scans[active_scan_id]+1;last_scan_id=active_scan_id;next_scan_id=next_scan_id+1;scan_open=0;
                $display("CONT_SCAN_LAST id=%0d pixels=%0d time_ps=%0t core_tick=%0d",active_scan_id,scan_count,$time,ticks);$fflush();
            end
        end
        if(pix_done_toggle!=done_seen)begin
            done_seen=pix_done_toggle;crc_scan_id=dut.scan_done_id;
            if(crc_scan_id<1 || crc_scan_id>FRAMES || crc_scan_id!=last_scan_id || crc_scan_id!=scan_crc_checks+1 || !pix_done_good || pix_done_crc!==result_crcs[crc_scan_id-1])
                $fatal(1,"CONT_SCAN_CRC id=%0d crc=%08x core_tick=%0d",crc_scan_id,pix_done_crc,ticks);
            scan_crc_checks=scan_crc_checks+1;
            $fdisplay(normal_trace,"D %0d %08x",crc_scan_id,pix_done_crc);
            $display("CONT_SCAN_CRC id=%0d CRC=%08x checks=%0d time_ps=%0t core_tick=%0d",crc_scan_id,pix_done_crc,scan_crc_checks,$time,ticks);$fflush();
        end
    end
    // DE continues even when a frame is blank: catch a missing valid refresh,
    // not only repeated IDs on valid scans. No demand exists after third scan.
    always @(posedge pix_out_clk)begin
        #1;
        if(rst_n && scans_started>0 && last_scan_id<FRAMES && pix_de && !pix_pixel_valid)
            $fatal(1,"CONT_BLANK_OR_PIXEL_GAP expected_scan_id=%0d input_frame=%0d core_tick=%0d",next_scan_id,frame,ticks);
    end

    task drive_continuous;
        integer x,y;
        begin
            @(negedge pix_in_clk);
            for(frame=1;frame<=FRAMES;frame=frame+1)begin
                if(last_input_start!=0 && ($time-last_input_start<PERIOD_PS || $time-last_input_start>PERIOD_PS+1))
                    $fatal(1,"CONT_INPUT_RATE frame=%0d gap_ps=%0t expected_floor=%0d",frame,$time-last_input_start,PERIOD_PS);
                last_input_start=$time;
                $display("CONT_INPUT_START frame=%0d time_ps=%0t core_tick=%0d continuous=1 ready_gating=0",frame,$time,ticks);$fflush();
                for(y=0;y<SIM_VT;y=y+1)for(x=0;x<SIM_HT;x=x+1)begin
                    pix_in_vsync_active=y<SIM_VS;
                    pix_in_de=y>=SIM_Y0 && y<SIM_Y0+H && x>=SIM_X0 && x<SIM_X0+W;
                    pix_in_rgb=pix_in_de ? expand565(sources[(frame-1)*N+(y-SIM_Y0)*W+x-SIM_X0]):0;
                    if(pix_in_de && (((y-SIM_Y0)*W+x-SIM_X0+1)%65536)==0)begin
                        $display("CONT_PROGRESS stage=input frame=%0d pixels=%0d captured=%0d core_tick=%0d",frame,(y-SIM_Y0)*W+x-SIM_X0+1,captured_frames,ticks);$fflush();
                    end
                    @(negedge pix_in_clk);
                end
            end
            // Natural SOF of the next raster closes capture3. No fourth active
            // frame is supplied in this bounded three-frame burst test.
            pix_in_vsync_active=1;pix_in_de=0;pix_in_rgb=0;
            repeat(SIM_VS*SIM_HT)@(negedge pix_in_clk);
            pix_in_vsync_active=0;drive_complete=1;
            $display("CONT_INPUT_ALL_SENT frames=%0d time_ps=%0t core_tick=%0d",FRAMES,$time,ticks);$fflush();
        end
    endtask
    task wait_presented(input integer ident);
        begin
            $display("WAIT_NATIVE_FULLSYSTEM_SCAN frame_id=%0d captured=%0d processed=%0d presented=%0d core_tick=%0d stop_wait=0",ident,captured_frames,processed_frames,presented_frames,ticks);$fflush();
            wait(last_scan_id>=ident && presented_frames>=ident);repeat(4)@(negedge core_clk);
            $display("VISIBLE_NATIVE_FULLSYSTEM frame_id=%0d scans=%0d scan_crc_checks=%0d core_tick=%0d",ident,scans[ident],scan_crc_checks,ticks);$fflush();
        end
    endtask
    integer overlap_cap_total=0,overlap_scan_total=0,triple_total=0,read_dual_total=0,write_dual_total=0;
    integer cap_aw_window=0,result_aw_window=0,sample_ar_window=0,display_ar_window=0;
    integer cap_active_window=0,scan_active_window=0,triple_window=0,read_dual_window=0,write_dual_window=0;
    integer cap_wait_other=0,result_wait_other=0,sample_wait_other=0,display_wait_other=0;
    integer engine_start_tick=0,engine_id_mon=0,engine_edges=0,engine_perf;
    reg engine_window_mon=0;
    initial begin
        engine_perf=$fopen("engine_overlap.csv","w");
        if(!engine_perf)$fatal(1,"cannot open engine overlap CSV");
        $fdisplay(engine_perf,"frame_id,begin_tick,done_tick,engine_edges,capture_active_cycles,scan_active_cycles,triple_active_cycles,read_dual_demand_cycles,write_dual_demand_cycles,capture_AW,result_AW,sample_AR,display_AR,capture_wait_result_owner,result_wait_capture_owner,sample_wait_display_owner,display_wait_sample_owner");
    end
    always @(posedge core_clk)begin
        if(rst_n)begin
            if(dut.bank_core.engine.begin_frame)begin
                if(engine_window_mon)$fatal(1,"CONT_ENGINE_OVERLAP_INVALID");
                engine_window_mon=1;engine_start_tick=ticks;engine_id_mon=frame_id_open;
                cap_aw_window=0;result_aw_window=0;sample_ar_window=0;display_ar_window=0;
                cap_active_window=0;scan_active_window=0;triple_window=0;read_dual_window=0;write_dual_window=0;
                cap_wait_other=0;result_wait_other=0;sample_wait_other=0;display_wait_other=0;
                $display("CONT_ENGINE_BEGIN id=%0d core_tick=%0d time_ps=%0t",engine_id_mon,ticks,$time);$fflush();
            end
            if(engine_window_mon)begin
                if(dut.input_link.input_dma.capture.capturing)begin cap_active_window=cap_active_window+1;overlap_cap_total=overlap_cap_total+1;end
                if(dut.output_video.frame_active)begin scan_active_window=scan_active_window+1;overlap_scan_total=overlap_scan_total+1;end
                if(dut.input_link.input_dma.capture.capturing && dut.output_video.frame_active)begin triple_window=triple_window+1;triple_total=triple_total+1;end
                if(dut.sample_valid && dut.display_arvalid)begin read_dual_window=read_dual_window+1;read_dual_total=read_dual_total+1;end
                if(dut.input_link.dma_awvalid && dut.input_link.core_awvalid)begin write_dual_window=write_dual_window+1;write_dual_total=write_dual_total+1;end
                if(dut.input_link.dma_awvalid && dut.input_link.dma_awready)cap_aw_window=cap_aw_window+1;
                if(dut.input_link.core_awvalid && dut.input_link.core_awready)result_aw_window=result_aw_window+1;
                if(dut.sample_valid && dut.sample_ready)sample_ar_window=sample_ar_window+1;
                if(dut.display_arvalid && dut.display_arready)display_ar_window=display_ar_window+1;
                if(dut.input_link.dma_awvalid && !dut.input_link.dma_awready && dut.input_link.shared_writes.state!=0 && dut.input_link.shared_writes.owner)cap_wait_other=cap_wait_other+1;
                if(dut.input_link.core_awvalid && !dut.input_link.core_awready && dut.input_link.shared_writes.state!=0 && !dut.input_link.shared_writes.owner)result_wait_other=result_wait_other+1;
                if(dut.sample_valid && !dut.sample_ready && dut.read_bus.state!=0 && !dut.read_bus.owner)sample_wait_other=sample_wait_other+1;
                if(dut.display_arvalid && !dut.display_arready && dut.read_bus.state!=0 && dut.read_bus.owner)display_wait_other=display_wait_other+1;
            end
        end
        #1;
        if(rst_n && engine_window_mon)begin
            engine_edges=ticks-engine_start_tick;
            if(dut.bank_core.engine.done)begin
                $display("CONT_ENGINE_DONE id=%0d core_tick=%0d engine_edges=%0d CRC=%08x cap_AW=%0d display_AR=%0d read_dual=%0d write_dual=%0d sample_wait_display=%0d result_wait_capture=%0d",engine_id_mon,ticks,engine_edges,dut.bank_core.engine.completed_crc,cap_aw_window,display_ar_window,read_dual_window,write_dual_window,sample_wait_other,result_wait_other);$fflush();
                $fdisplay(engine_perf,"%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d",engine_id_mon,engine_start_tick,ticks,engine_edges,cap_active_window,scan_active_window,triple_window,read_dual_window,write_dual_window,cap_aw_window,result_aw_window,sample_ar_window,display_ar_window,cap_wait_other,result_wait_other,sample_wait_other,display_wait_other);$fflush();
                engine_window_mon=0;
            end
            if(NATIVE && engine_edges*64'd60>125000000)begin
                $display("CONT_FIRST_BOTTLENECK ENGINE_60_BUDGET id=%0d core_tick=%0d engine_edges=%0d done=%0d capture_AW=%0d display_AR=%0d read_dual=%0d write_dual=%0d sample_wait_display=%0d result_wait_capture=%0d fifo_used=%0d input_frame=%0d",engine_id_mon,ticks,engine_edges,dut.bank_core.engine.done,cap_aw_window,display_ar_window,read_dual_window,write_dual_window,sample_wait_other,result_wait_other,fifo_used,frame);$fflush();
                $fatal(1,"CONT_ENGINE_60_BUDGET");
            end
        end
    end
    always @(posedge pix_in_clk)begin
        #1;
        if(rst_n && (dut.input_link.input_dma.capture.bad!=0 || dut.input_link.input_dma.capture.no_grant_bin!=0))begin
            $display("CONT_FIRST_BOTTLENECK CAPTURE_INPUT id=%0d core_tick=%0d time_ps=%0t bad=%h no_grant=%0d count=%0d fifo_used=%0d",frame,ticks,$time,dut.input_link.input_dma.capture.bad,dut.input_link.input_dma.capture.no_grant_bin,dut.input_link.input_dma.capture.pixel_count,fifo_used);$fflush();
            $fatal(1,"CONT_CAPTURE_INPUT_CAPACITY");
        end
    end

    reg [8*1024-1:0] source_path,expected_path,source_crc_path,expected_crc_path;
    initial begin
        if((!NATIVE && !CONT_PILOT_MODE) || CACHE_PROFILE!=2 || FRAMES!=3 || CHECKER_TEST<0 || CHECKER_TEST>2 ||
            PIX_HZ!=148500000 || FU>STRIDE ||
            SIM_HT<SIM_X0+W || SIM_VT<SIM_Y0+H)
            $fatal(1,"native fullsystem profile/timing/stride fixture mismatch");
        $display("LOAD_NATIVE_FULLSYSTEM_FIXTURE width=%0d height=%0d PIX_HZ=%0d frames=%0d TRACE_PIXELS=%0d",W,H,PIX_HZ,FRAMES,TRACE_PIXELS);$fflush();
        for(i=0;i<4*FB;i=i+1)memory[i]=0;
        for(i=0;i<4;i=i+1)scans[i]=0;
        source_path="source256.mem";expected_path="expected.mem";
        source_crc_path="sourcecrc.mem";expected_crc_path="expectedcrc.mem";
        if($value$plusargs("SOURCE_MEM=%s",source_path))begin end
        if($value$plusargs("EXPECTED_MEM=%s",expected_path))begin end
        if($value$plusargs("SOURCE_CRC_MEM=%s",source_crc_path))begin end
        if($value$plusargs("EXPECTED_CRC_MEM=%s",expected_crc_path))begin end
        $readmemh(source_path,packed_source);$readmemh(expected_path,goldens);
        $readmemh(source_crc_path,source_crcs);$readmemh(expected_crc_path,result_crcs);
        for(i=0;i<FRAMES*N;i=i+1)begin
            sources[i]=packed_source[i/16][(i%16)*16+:16];
            if((^sources[i])===1'bx || (^goldens[i])===1'bx)$fatal(1,"missing native stimulus/golden pixel%0d",i);
        end
        for(i=0;i<FRAMES;i=i+1)if((^source_crcs[i])===1'bx || (^result_crcs[i])===1'bx)$fatal(1,"missing perframe CRC fixture%0d",i);
        $display("FIXTURE_READY_NATIVE_FULLSYSTEM width=%0d height=%0d PIX_HZ=%0d HT=%0d VT=%0d source_crc=%08x corrected_crc=%08x DDR_preloaded=0 stop_wait=0 camera_rate_claim=0",W,H,PIX_HZ,SIM_HT,SIM_VT,source_crcs[0],result_crcs[0]);$fflush();
        normal_trace=$fopen("normal.trace","w");perf_file=$fopen("process.csv","w");
        if(normal_trace==0 || perf_file==0)$fatal(1,"cannot open output artifacts");
        $fdisplay(perf_file,"cache_profile,frame_id,legacy_cycles,legacy_cycles_plus1,source_to_publish_notification_edges,cache_hits_delta,cache_misses_delta,cache_queries_delta,refill_busy_cycles,scatter_cycles,query_reads_during_scatter,sample_ar_stall_cycles,sample_response_beats,dropped_total,scan_repeat_total,no_free_total,model_expected_misses,model_miss_match,observed_inbounds_refs,model_expected_inbounds_refs,model_reference_match");
        repeat(20)@(negedge core_clk);rst_n=1;repeat(30)@(negedge core_clk);
        capture_admit=1;scan_enable=1;
        gamma_enable=0;correction_enable=1;
        drive_continuous();wait_presented(FRAMES);
        normal_done=1;
        if(captured_frames!=FRAMES || processed_frames!=FRAMES || presented_frames!=FRAMES ||
            commits!=FRAMES || publishes!=FRAMES || scan_crc_checks!=FRAMES || scans_started!=FRAMES ||
            frame_open || underflows || mismatches || dut.dropped_frames || dut.overflow_frames || dut.no_free_frames)
            $fatal(1,"native fullsystem corrected frame counts/scan CRC mismatch");
        for(i=1;i<=FRAMES;i=i+1)if(scans[i]!=1)$fatal(1,"CONT_SCAN_MISSING_OR_REPEAT id=%0d scans=%0d",i,scans[i]);
        $fclose(normal_trace);$fclose(perf_file);
        $display("METRICS cache_profile=%0d captured=%0d processed=%0d presented=%0d scans1=%0d scans2=%0d scans3=%0d repeats=%0d dropped=%0d overflow=%0d no_free=%0d hits=%0d misses=%0d queries=%0d ticks=%0d",CACHE_PROFILE,captured_frames,processed_frames,presented_frames,scans[1],scans[2],scans[3],scan_repeat_frames,dut.dropped_frames,dut.overflow_frames,dut.no_free_frames,cache_hits,cache_misses,queries,ticks);
        if(overlap_cap_total==0 || overlap_scan_total==0 || triple_total==0 || (read_dual_total==0 && write_dual_total==0))
            $fatal(1,"CONT_OVERLAP_NOT_EXERCISED capture=%0d scan=%0d triple=%0d read_dual=%0d write_dual=%0d",overlap_cap_total,overlap_scan_total,triple_total,read_dual_total,write_dual_total);
        $display("CONT_OVERLAP capture=%0d scan=%0d triple=%0d read_dual=%0d write_dual=%0d",overlap_cap_total,overlap_scan_total,triple_total,read_dual_total,write_dual_total);
        $display("PASS_CONTINUOUS_THREE_FRAMES profile=%0d frames=%0d width=%0d height=%0d PIX_HZ=%0d NATIVE=%0d checker_test=%0d stop_wait=0 full_pixel_CRC_ID=1",CACHE_PROFILE,FRAMES,W,H,PIX_HZ,NATIVE,CHECKER_TEST);$fflush();
        $finish;
    end
    initial begin #(64'd8000*MAX_CYCLES);$fatal(1,"bounded native fullsystem watchdog");end
endmodule
