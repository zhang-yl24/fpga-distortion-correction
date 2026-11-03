`timescale 1ns/1ps
// Actual complete engine: preloaded source DDR -> rotation/Brown/cache ->
// bilinear/gammaOFF/writer -> DDR. Capture/HDMI/scan/PHY/E2E are excluded.
module tb_native_correction_engine;
    parameter CACHE_PROFILE=1,WIDTH=1920,HEIGHT=1080,FRAMES=1,TRACE_WRITES=1,PILOT_PIXELS=0;
    parameter MAX_CYCLES=20000000;
    parameter [27:0] SOURCE_BASE=28'h0000000,OUTPUT_BASE=28'h0100000;
    localparam N=WIDTH*HEIGHT,BEATS=N/16,BURSTS=N/256,FRAME_UNITS=N/2;
    localparam NATIVE=WIDTH==1920 && HEIGHT==1080;
    `include "board1080-penn.vh"
    reg clk=0;always #4 clk=~clk;
    reg rst_n=0,frame_valid=0;
    reg gamma_enable=0,correction_enable=1;
    reg [27:0] source_base=SOURCE_BASE,output_base=OUTPUT_BASE;
    reg [31:0] frame_id=32'ha1100001;
    wire frame_ready,done,failed;wire [7:0] fault;
    wire [1:0] gamma_mode;wire [31:0] gamma_frames;
    wire [27:0] araddr,awaddr,completed_base;wire [3:0] arlen,awlen;
    wire arvalid,awvalid;reg arready=0,awready=0,wready=0,wlast=0;
    wire [255:0] wdata;wire [31:0] wstrb;
    reg [255:0] rdata=0;reg rvalid=0,rlast=0;reg [3:0] rid=0;
    wire [31:0] completed_id,completed_crc,hits,misses,completed_queries;
    pipeline_gamma_frame_engine_1080_geometry_bypass #(.WIDTH(WIDTH),.HEIGHT(HEIGHT),
        .TIMEOUT_BITS(26),.MAX_RADIUS_Q22(B1080_RADIUS_Q22),
        .RASTER_DOUBLE_BUFFER(1),.CACHE_PROFILE(CACHE_PROFILE)) dut(
        .clk(clk),.rst_n(rst_n),.frame_valid(frame_valid),.frame_ready(frame_ready),
        .gamma_enable(gamma_enable),.correction_enable(correction_enable),.gamma_mode(gamma_mode),.gamma_frames(gamma_frames),
        .source_base(source_base),.output_base(output_base),.frame_id(frame_id),
        .cfg_out_cx(B1080_OUT_CX),.cfg_out_cy(B1080_OUT_CY),.cfg_src_cx(B1080_SRC_CX),.cfg_src_cy(B1080_SRC_CY),
        .cfg_src_fx(B1080_SRC_FX),.cfg_src_fy(B1080_SRC_FY),.cfg_inv_fx(B1080_INV_FX),.cfg_inv_fy(B1080_INV_FY),
        .cfg_k1(B1080_K1),.cfg_k2(B1080_K2),.cfg_k3(B1080_K3),.cfg_p1(B1080_P1),.cfg_p2(B1080_P2),
        .cfg_rot_cx(B1080_ROT_CX),.cfg_rot_cy(B1080_ROT_CY),.cfg_rot_cos(B1080_ROT_COS),.cfg_rot_sin(B1080_ROT_SIN),
        .araddr(araddr),.arlen(arlen),.arvalid(arvalid),.arready(arready),
        .rdata(rdata),.rvalid(rvalid),.rlast(rlast),.rid(rid),
        .awaddr(awaddr),.awlen(awlen),.awvalid(awvalid),.awready(awready),
        .wdata(wdata),.wstrb(wstrb),.wready(wready),.wlast(wlast),
        .done(done),.failed(failed),.fault(fault),.completed_base(completed_base),
        .completed_id(completed_id),.completed_crc(completed_crc),.hits(hits),.misses(misses),.completed_queries(completed_queries));

    // Exactly two compact frame regions, independent of the numerical base gap.
    // Source fixture is256bits/line; golden is16bits/pixel and is never DUT data.
    reg [255:0] memory[0:2*BEATS-1];
    reg [15:0] golden[0:N-1];
    reg [31:0] source_crc_manifest[0:0],expected_crc[0:0];
    function automatic integer location(input [27:0] address);
        begin
            if(address[2:0]!=0)$fatal(1,"DDR beat address not32-byte aligned %h",address);
            if(address>=SOURCE_BASE && address<SOURCE_BASE+FRAME_UNITS)
                location=(address-SOURCE_BASE)>>3;
            else if(address>=OUTPUT_BASE && address<OUTPUT_BASE+FRAME_UNITS)
                location=BEATS+((address-OUTPUT_BASE)>>3);
            else begin $fatal(1,"DDR address outside source/destination regions %h",address);location=0;end
        end
    endfunction
    integer ticks=0,rleft=0,rindex=0,wleft=0;
    reg [27:0] next_waddr=0;
    // Same deterministic service/backpressure rules as the accepted fullpipe.
    always @(negedge clk)begin
        ticks=ticks+1;
        arready=rst_n && rleft==0 && ticks%7!=0;
        rvalid=rst_n && rleft!=0 && ticks%3!=0;
        rlast=rleft==1;rid=0;
        if(rvalid)rdata=memory[rindex];
        awready=rst_n && wleft==0 && ticks%7>=2;
        wready=rst_n && (wleft!=0 || (awvalid && awready)) && ticks%5!=0;
        wlast=wleft!=0 ? wleft==1:awlen==0;
    end

    wire refill_busy,scatter_active,read_during_scatter;
    generate if(CACHE_PROFILE==2)begin: observe_runtime
        assign refill_busy=dut.core.sampler.runtime_cache.cache.store_fill_busy;
        assign scatter_active=dut.core.sampler.runtime_cache.cache.store.scatter_write;
        assign read_during_scatter=scatter_active && dut.core.sampler.runtime_cache.cache.store.read_fire;
    end else begin: observe_scatter16
        wire [3:0] state=dut.core.sampler.serial_cache.cache.widened_fill.inner.state;
        assign refill_busy=state==2 || state==3 || state==4;
        assign scatter_active=state==4;
        assign read_during_scatter=1'b0;
    end endgenerate
    integer active=0,start_tick=0,done_frames=0;
    reg [31:0] active_id=0;
    reg pilot_stop_pending=0;
    integer first_w_tick=0,last_w_tick=0;
    integer hits_start=0,misses_start=0,queries_start=0;
    integer ar_bursts=0,rbeats=0,aw_bursts=0,wbeats=0,pixels_checked=0;
    integer ar_stalls=0,r_waits=0,aw_stalls=0,w_stalls=0,writer_stalls=0,coordinate_stalls=0;
    integer refill_cycles=0,scatter_cycles=0,overlap_reads=0;
    integer perf_file,write_trace=0,old_wleft,lane,pixel_index,write_index;
    integer begin_to_done_edges=0;
    integer model_expected_misses=NATIVE ? 16200:-1;
    integer model_expected_refs=NATIVE ? 7945462:-1;
    integer model_miss_match=-1,model_reference_match=-1;
    reg accept_aw,transfer,held_ar=0,held_aw=0,held_w=0;
    reg [31:0] saved_ar,saved_aw;reg [287:0] saved_w;
    reg [27:0] write_address;
    always @(posedge clk)begin
        if(!rst_n)begin
            rleft<=0;rindex<=0;wleft<=0;next_waddr<=0;active=0;
            held_ar=0;held_aw=0;held_w=0;
        end else begin
            if(failed)$fatal(1,"native engine failed profile=%0d fault=%h",CACHE_PROFILE,fault);
            if(held_ar && (!arvalid || {arlen,araddr}!==saved_ar))$fatal(1,"AR hold violation");
            if(held_aw && (!awvalid || {awlen,awaddr}!==saved_aw))$fatal(1,"AW hold violation");
            if(held_w && {wstrb,wdata}!==saved_w)$fatal(1,"W payload changed under backpressure");
            held_ar=arvalid && !arready;saved_ar={arlen,araddr};
            held_aw=awvalid && !awready;saved_aw={awlen,awaddr};
            held_w=(wleft!=0 || awvalid) && !wready;saved_w={wstrb,wdata};
            if(dut.begin_frame)begin
                if(active || rleft!=0 || wleft!=0)$fatal(1,"frame began before prior transaction drain");
                active=1;active_id=frame_id;start_tick=ticks;
                pilot_stop_pending=0;
                hits_start=hits;misses_start=misses;queries_start=completed_queries;
                ar_bursts=0;rbeats=0;aw_bursts=0;wbeats=0;pixels_checked=0;
                ar_stalls=0;r_waits=0;aw_stalls=0;w_stalls=0;writer_stalls=0;coordinate_stalls=0;
                refill_cycles=0;scatter_cycles=0;overlap_reads=0;first_w_tick=0;last_w_tick=0;
                $display("BEGIN_NATIVE_ENGINE profile=%0d frame_id=%0d tick=%0d",CACHE_PROFILE,frame_id,ticks);
                $fflush();
            end
            if(active)begin
                if(ticks-start_tick>MAX_CYCLES)$fatal(1,"bounded native engine cycle watchdog");
                if(arvalid && !arready)ar_stalls=ar_stalls+1;
                if(rleft!=0 && !rvalid)r_waits=r_waits+1;
                if(awvalid && !awready)aw_stalls=aw_stalls+1;
                if((wleft!=0 || awvalid) && !wready)w_stalls=w_stalls+1;
                if(dut.tone_valid && !dut.tone_ready)writer_stalls=writer_stalls+1;
                if(dut.coordinate_valid && !dut.coordinate_ready)coordinate_stalls=coordinate_stalls+1;
                if(refill_busy)refill_cycles=refill_cycles+1;
                if(scatter_active)scatter_cycles=scatter_cycles+1;
                if(read_during_scatter)overlap_reads=overlap_reads+1;
            end
            if(arvalid && arready)begin
                if(!active || rleft!=0 || arlen!==7 || araddr<SOURCE_BASE ||
                    araddr+64>SOURCE_BASE+FRAME_UNITS || (araddr-SOURCE_BASE)%64!=0)
                    $fatal(1,"source AR bounds/order/length/overlap");
                rleft<=arlen+1;rindex<=location(araddr);ar_bursts=ar_bursts+1;
            end
            if(rvalid)begin
                if(!active || rleft<=0 || rindex<0 || rindex>=BEATS || rlast!==(rleft==1))
                    $fatal(1,"R beat outside active source transaction");
                rleft<=rleft-1;rindex<=rindex+1;rbeats=rbeats+1;
            end
            old_wleft=wleft;accept_aw=awvalid && awready;
            transfer=wready && (old_wleft!=0 || accept_aw);
            if(accept_aw)begin
                if(!active || old_wleft!=0 || awlen!==15 || awaddr!==OUTPUT_BASE+aw_bursts*128 ||
                    awaddr+128>OUTPUT_BASE+FRAME_UNITS)
                    $fatal(1,"destination AW complete raster identity/order/length");
                aw_bursts=aw_bursts+1;
                wleft<=awlen+1-(transfer ? 1:0);next_waddr<=awaddr+(transfer ? 8:0);
            end else if(transfer)begin wleft<=old_wleft-1;next_waddr<=next_waddr+8;end
            if(transfer)begin
                write_address=old_wleft!=0 ? next_waddr:awaddr;
                if(!active || write_address!==OUTPUT_BASE+wbeats*8 || wstrb!==32'hffffffff ||
                    wlast!==(old_wleft!=0 ? old_wleft==1:awlen==0))
                    $fatal(1,"W address/strobe/last mismatch beat=%0d",wbeats);
                write_index=location(write_address);
                for(lane=0;lane<16;lane=lane+1)begin
                    pixel_index=(write_address-OUTPUT_BASE)*2+lane;
                    if(pixel_index<0 || pixel_index>=N || wdata[lane*16+:16]!==golden[pixel_index])
                        $fatal(1,"native wholeframe golden mismatch profile=%0d pixel=%0d addr=%h lane=%0d got=%h expected=%h",CACHE_PROFILE,pixel_index,write_address,lane,wdata[lane*16+:16],golden[pixel_index]);
                end
                memory[write_index]<=wdata;
                if(TRACE_WRITES)$fdisplay(write_trace,"%0d %07x %064x",active_id,write_address,wdata);
                if(wbeats==0)first_w_tick=ticks;
                wbeats=wbeats+1;pixels_checked=pixels_checked+16;last_w_tick=ticks;
                if(pixels_checked%65536==0)begin
                    $display("PROGRESS_NATIVE_ENGINE profile=%0d frame_id=%0d core_ticks=%0d written=%0d done=%0d AR=%0d R=%0d AW=%0d W=%0d",CACHE_PROFILE,active_id,ticks-start_tick,pixels_checked,done,ar_bursts,rbeats,aw_bursts,wbeats);
                    $fflush();
                end
                if(PILOT_PIXELS!=0 && pixels_checked>=PILOT_PIXELS)pilot_stop_pending=1;
            end
            // Sample done after nonblocking assignments on THIS accepted edge.
            // This avoids charging an extra observer/notification clock cycle.
            #1;
            if(failed)$fatal(1,"native engine post-edge fault=%h",fault);
            if(done)begin
                if(!active || completed_id!==active_id || completed_base!==OUTPUT_BASE ||
                    completed_crc!==expected_crc[0] || gamma_mode!==0 ||
                    pixels_checked!=N || wbeats!=BEATS || aw_bursts!=BURSTS ||
                    dut.writer_pixels!=N || dut.writer_beats!=BEATS ||
                    rleft!=0 || wleft!=0 || arvalid || awvalid || completed_queries-queries_start!=N ||
                    rbeats!=8*ar_bursts || misses-misses_start!=ar_bursts ||
                    scatter_cycles!=(CACHE_PROFILE==1 ? 16:32)*ar_bursts)
                    $fatal(1,"native complete ID/CRC/counter/drain mismatch q=%0d misses=%0d AR=%0d W=%0d CRC=%h",completed_queries-queries_start,misses-misses_start,ar_bursts,wbeats,completed_crc);
                if(NATIVE)begin
                    model_miss_match=(misses-misses_start)==model_expected_misses;
                    model_reference_match=(hits-hits_start+misses-misses_start)==model_expected_refs;
                    if(!model_miss_match || !model_reference_match)
                        $display("NATIVE_MODEL_MISMATCH profile=%0d observed_misses=%0d model_expected_misses=%0d model_miss_match=%0d observed_inbounds_refs=%0d model_expected_inbounds_refs=%0d model_reference_match=%0d",CACHE_PROFILE,misses-misses_start,model_expected_misses,model_miss_match,hits-hits_start+misses-misses_start,model_expected_refs,model_reference_match);
                end
                begin_to_done_edges=ticks-start_tick;done_frames=done_frames+1;
                $fdisplay(perf_file,"%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d",CACHE_PROFILE,active_id,start_tick,ticks,begin_to_done_edges,begin_to_done_edges+1,hits-hits_start,misses-misses_start,completed_queries-queries_start,ar_bursts,rbeats,ar_stalls,r_waits,aw_bursts,wbeats,aw_stalls,w_stalls,writer_stalls,coordinate_stalls,refill_cycles,scatter_cycles,overlap_reads,first_w_tick-start_tick,last_w_tick-start_tick,model_expected_misses,model_miss_match,hits-hits_start+misses-misses_start,model_expected_refs,model_reference_match);
                $display("METRICS cache_profile=%0d frame_id=%0d begin_to_done_edges=%0d pixels_checked=%0d hits=%0d observed_misses=%0d queries=%0d AR=%0d R=%0d AW=%0d W=%0d AR_stalls=%0d R_wait_cycles=%0d AW_stalls=%0d W_stalls=%0d writer_stalls=%0d coordinate_stalls=%0d refill_busy_cycles=%0d scatter_cycles=%0d query_reads_during_scatter=%0d completed_crc=%08x model_expected_misses=%0d model_miss_match=%0d observed_inbounds_refs=%0d model_expected_inbounds_refs=%0d model_reference_match=%0d",CACHE_PROFILE,active_id,begin_to_done_edges,pixels_checked,hits-hits_start,misses-misses_start,completed_queries-queries_start,ar_bursts,rbeats,aw_bursts,wbeats,ar_stalls,r_waits,aw_stalls,w_stalls,writer_stalls,coordinate_stalls,refill_cycles,scatter_cycles,overlap_reads,completed_crc,model_expected_misses,model_miss_match,hits-hits_start+misses-misses_start,model_expected_refs,model_reference_match);
                active=0;
                $fflush();
            end else if(pilot_stop_pending)begin
                // Intentional partial transaction stop. Pending DDR/cache state
                // may remain; neither full-frame done nor final CRC is claimed.
                if(done_frames!=0 || !active || pixels_checked!=PILOT_PIXELS)
                    $fatal(1,"pilot stop mixed with full completion");
                $display("PASS_NATIVE_ENGINE_PILOT cache_profile=%0d frame_id=%0d written_pixels=%0d core_ticks=%0d done=%0d AR=%0d R=%0d AW=%0d W=%0d writer_stalls=%0d full_frame=0",CACHE_PROFILE,active_id,pixels_checked,ticks-start_tick,done,ar_bursts,rbeats,aw_bursts,wbeats,writer_stalls);
                $fflush();$fclose(perf_file);if(TRACE_WRITES)$fclose(write_trace);
                $finish;
            end
        end
    end

    reg [8191:0] source_path,expected_path,source_crc_path,expected_crc_path;
    integer i,f;
    initial begin
        if((CACHE_PROFILE!=1 && CACHE_PROFILE!=2) || FRAMES<1 || FRAMES>2 || N%256!=0 ||
            (PILOT_PIXELS!=0 && (PILOT_PIXELS>=N || PILOT_PIXELS%16!=0 || FRAMES!=1)) ||
            {1'b0,SOURCE_BASE}+FRAME_UNITS>{1'b0,OUTPUT_BASE} ||
            {1'b0,OUTPUT_BASE}+FRAME_UNITS>29'h10000000)
            $fatal(1,"native engine fixture parameter/layout mismatch");
        source_path="source256.mem";expected_path="expected.mem";
        source_crc_path="sourcecrc.mem";expected_crc_path="expectedcrc.mem";
        if($value$plusargs("SOURCE_MEM=%s",source_path))begin end
        if($value$plusargs("EXPECTED_MEM=%s",expected_path))begin end
        if($value$plusargs("SOURCE_CRC_MEM=%s",source_crc_path))begin end
        if($value$plusargs("EXPECTED_CRC_MEM=%s",expected_crc_path))begin end
        for(i=BEATS;i<2*BEATS;i=i+1)memory[i]=0;
        $readmemh(source_path,memory,0,BEATS-1);$readmemh(expected_path,golden);
        $readmemh(source_crc_path,source_crc_manifest);$readmemh(expected_crc_path,expected_crc);
        for(i=0;i<BEATS;i=i+1)if((^memory[i])===1'bx)$fatal(1,"source fixture missing/unknown beat%0d",i);
        for(i=0;i<N;i=i+1)if((^golden[i])===1'bx)$fatal(1,"golden fixture missing/unknown pixel%0d",i);
        if((^source_crc_manifest[0])===1'bx || (^expected_crc[0])===1'bx)$fatal(1,"missing CRC fixture");
        perf_file=$fopen("process.csv","w");if(!perf_file)$fatal(1,"cannot open process.csv");
        if(TRACE_WRITES)begin write_trace=$fopen("writes.trace","w");if(!write_trace)$fatal(1,"cannot open writes.trace");end
        $fdisplay(perf_file,"cache_profile,frame_id,begin_edge_tick,done_edge_tick,begin_to_done_edges,inclusive_active_edges,cache_hits,observed_misses,cache_queries,AR_bursts,R_beats,AR_stalls,R_wait_cycles,AW_bursts,W_beats,AW_stalls,W_stalls,writer_input_stalls,coordinate_stalls,refill_busy_cycles,scatter_cycles,query_reads_during_scatter,first_W_edge_distance,last_W_edge_distance,model_expected_misses,model_miss_match,observed_inbounds_refs,model_expected_inbounds_refs,model_reference_match");
        $display("FIXTURE_READY width=%0d height=%0d source_crc_manifest=%08x expected_crc=%08x source_preloaded=1 capture=0 hdmi=0 scan=0 E2E=0",WIDTH,HEIGHT,source_crc_manifest[0],expected_crc[0]);
        $fflush();
        repeat(8)@(negedge clk);rst_n=1;
        for(f=1;f<=FRAMES;f=f+1)begin
            @(negedge clk);while(!frame_ready)@(negedge clk);
            frame_id=32'ha1100000+f;frame_valid=1;
            @(posedge clk);if(!frame_ready)$fatal(1,"frame_ready withdrew before accept");
            @(negedge clk);frame_valid=0;
            @(negedge clk);while(done_frames<f)@(negedge clk);
        end
        repeat(4)@(negedge clk);
        if(done_frames!=FRAMES || active || failed)$fatal(1,"native final frame conservation");
        $fclose(perf_file);if(TRACE_WRITES)$fclose(write_trace);
        $display("PASS_NATIVE_CORRECTION_ENGINE profile=%0d frames=%0d width=%0d height=%0d model_miss_match=%0d model_reference_match=%0d preloadedDDR_complete_engine_only",CACHE_PROFILE,FRAMES,WIDTH,HEIGHT,model_miss_match,model_reference_match);
        $finish;
    end
    initial begin #(8.0*(MAX_CYCLES*FRAMES+100000));$fatal(1,"bounded native engine global watchdog");end
endmodule
