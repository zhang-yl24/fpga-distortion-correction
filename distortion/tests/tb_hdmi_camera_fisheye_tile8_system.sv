// TILE8/DUALSTRIPE: selected S3 pixel oracle, KEY events, ownership and drain checks retained.
`timescale 1ps/1ps
// Raw RGB/control -> real sampler -> DMA/DDR -> frame-locked fisheye/identity -> actual
// output FIFO and pixel scan. Input148.5MHz/output74.25MHz; no physical PHY claim.
module tb_hdmi_camera_fisheye_tile8_system;
    `include "config.vh"
    `include "timing.vh"
    localparam W=VEC_WIDTH,H=VEC_HEIGHT,N=W*H,FB=N/16,FU=N/2,STRIDE=1048576;
    localparam NATIVE=W==1920&&H==1080,SMALL=W==32&&H==16;
    localparam [63:0] PERIOD_PS=(64'd2000000*SIM_HT*SIM_VT)/297;
    reg core_clk=0,pix_in_clk=0,pix_out_clk=0;
    reg c_aw_seen_valid=0;
    always #4000 core_clk=~core_clk;
    integer in_phase=0,in_delay,out_phase=0,out_delay;
    initial forever begin
        in_phase=in_phase+1000000;in_delay=in_phase/297;in_phase=in_phase%297;
        #(in_delay)pix_in_clk=~pix_in_clk;
    end
    initial begin
        #(SIM_OUTPUT_PHASE_PS);
        forever begin
            out_phase=out_phase+2000000;out_delay=out_phase/297;out_phase=out_phase%297;
            #(out_delay)pix_out_clk=~pix_out_clk;
        end
    end
    reg rst_n=0,capture_admit=0,scan_enable=0,external_fault=0;
    reg [7:0] external_fault_code=0;
    reg raw_vs=0,raw_hs=0,raw_de=0;reg [23:0] raw_rgb=0;
    wire pix_in_vsync_active,pix_in_de,sampled_valid;
    wire sampled_vs,sampled_hs,sampled_de;wire [23:0] pix_in_rgb;
    hdmi_camera_pixel_sampler #(.VS_ACTIVE_LEVEL(1),.DE_ACTIVE_LEVEL(1)) input_sampler(
        .pclk(pix_in_clk),.rst_n(rst_n),.raw_vs(raw_vs),.raw_hs(raw_hs),.raw_de(raw_de),.raw_rgb(raw_rgb),
        .sampled_vs(sampled_vs),.sampled_hs(sampled_hs),.sampled_de(sampled_de),
        .sampled_rgb(pix_in_rgb),.sampled_valid(sampled_valid),
        .vs_active(pix_in_vsync_active),.de_active(pix_in_de));
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
    reg key1_n=1;wire corrected_requested,toggle_pulse;
    camera720_view_control #(.DEBOUNCE_CYCLES(4)) view_control(
        .clk(core_clk),.rst_n(rst_n),.key1_n(key1_n),.corrected_requested(corrected_requested),.toggle_pulse(toggle_pulse));
    hdmi_camera_fisheye_system #(.WIDTH(W),.HEIGHT(H),.BANK_STRIDE(STRIDE),
        .HT(SIM_HT),.VT(SIM_VT),.HS(SIM_HS),.VS(SIM_VS),.X0(SIM_X0),.Y0(SIM_Y0)) dut(
        .core_clk(core_clk),.pix_in_clk(pix_in_clk),.pix_out_clk(pix_out_clk),.rst_n(rst_n),
        .capture_admit(capture_admit),.scan_enable(scan_enable),.external_fault(external_fault),.external_fault_code(external_fault_code),
        .pix_in_vsync_active(pix_in_vsync_active),.pix_in_de(pix_in_de),.pix_in_rgb(pix_in_rgb),
        .cfg_corrected(corrected_requested),
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

    // Four logical frame regions, addressed by bank/offset, not preloaded.
    reg [255:0] memory[0:4*FB-1];
    reg [15:0] sources[0:3*N-1],goldens[0:3*N-1];reg masks[0:3*N-1];
    reg [255:0] source_words[0:3*FB-1],result_words[0:3*FB-1];
    reg [31:0] source_crcs[0:2],result_crcs[0:2];
    integer phase_id=0,ticks=0,tx_frame=-1,tx_x,tx_y;
    reg source_window_closed=0,previous_in_vs=0;
    integer source_epoch[0:1],result_epoch[0:1],source_bank_for[0:7],result_bank_for[0:7];
    integer input_pixels[0:7],source_written[0:7],result_written[0:7],readback_beats[0:7];
    integer commits[0:7],releases[0:7],publications[0:7],unique_scans[0:7],scan_pixels[0:7];
    reg [31:0] observed_source_crc[0:7],observed_scan_crc[0:7];
    integer begins[0:7],fills[0:7],scatter_cycles[0:7],process_cycles[0:7],future_capture_overlap[0:7];
    reg [63:0] sof_ps[0:8],first_ps[0:7],last_ps[0:7],commit_ps[0:7],release_ps[0:7],publish_ps[0:7];
    reg [63:0] scan_start_ps[0:7],scan_last_ps[0:7],scan_done_ps[0:7];
    integer rleft=0,rindex=0,rbank=0,rframe=-1,wleft=0,windex=0,wbank=0,wframe=-1;
    integer total_source_beats=0,total_result_beats=0,total_readback_beats=0;
    integer commit_total=0,release_total=0,publish_total=0,unique_total=0;
    integer aw_stall=0,w_stall=0,physical_ar_stall=0,cache_output_stall=0,core_output_stall=0,writer_input_stall=0;
    integer write_contention=0,read_contention=0,peak_input_fifo=0,peak_output_fifo=0,peak_cache_lines=0;
    // One bounded SMALL-only selected-address hold for each arbiter. These
    // coverage stalls never affect the native input/output or ready cadence.
    localparam FORCE_HOLD_LIMIT=20000;
    reg forced_result_aw_done=0,forced_display_ar_done=0;
    integer forced_result_aw_hold_cycles=0,forced_display_ar_hold_cycles=0;
    integer forced_write_dual_clients_seen=0,forced_read_dual_clients_seen=0;
    reg [127:0] cache_lines_seen=0;integer live_cache_lines=0;
    reg heldar=0,heldaw=0,heldw=0,heldresult=0;
    reg [27:0] saved_ar,saved_aw;reg [3:0] saved_arlen,saved_awlen;
    reg [255:0] saved_w;reg [15:0] saved_result565;reg [23:0] saved_tag;
    reg previous_release=0,previous_publish=0,previous_commit=0;
    integer events,frames_csv,scans_csv,summary,i,j,k,f,bank,off,tf,tb,ti,to;
    integer coordinates_issued[0:7],scan_active_cycles[0:7],coordinate_blocked_cycles[0:7];
    integer tail_drain_cycles[0:7],writer_blocked_cycles[0:7],cache_ar_wait_cycles[0:7],cache_r_wait_cycles[0:7];
    integer performance_csv,metric_frame,oracle_x,oracle_y,oracle_tile;
    // Observational counters may overlap; no counter changes UART or RTL ports.
    always @(posedge core_clk)if(rst_n&&phase_id==0&&processing)begin
        metric_frame=dut.bank_core.accepted_id-1;
        if(metric_frame<0||metric_frame>=8)$fatal(1,"invalid metric frame");
        if(dut.bank_core.engine.state==1)begin
            scan_active_cycles[metric_frame]=scan_active_cycles[metric_frame]+1;
            if(dut.bank_core.engine.coordinate_ready)begin
                if(dut.bank_core.active_corrected)begin
                    oracle_tile=coordinates_issued[metric_frame]/64;
                    oracle_x=(oracle_tile%(W/8))*8+coordinates_issued[metric_frame]%8;
                    oracle_y=(oracle_tile/(W/8))*8+(coordinates_issued[metric_frame]%64)/8;
                end else begin
                    oracle_x=coordinates_issued[metric_frame]%W;oracle_y=coordinates_issued[metric_frame]/W;
                end
                if(coordinates_issued[metric_frame]>=N||dut.bank_core.engine.raster_tag!==oracle_y*W+oracle_x||
                   dut.bank_core.engine.column!==oracle_x||dut.bank_core.engine.row!==oracle_y||
                   dut.bank_core.engine.tiled_mode!==dut.bank_core.active_corrected)
                    $fatal(1,"independent system tile/raster emission mismatch frame=%0d issue=%0d",metric_frame,coordinates_issued[metric_frame]);
                coordinates_issued[metric_frame]=coordinates_issued[metric_frame]+1;
            end else coordinate_blocked_cycles[metric_frame]=coordinate_blocked_cycles[metric_frame]+1;
        end
        if(dut.bank_core.engine.state==2)tail_drain_cycles[metric_frame]=tail_drain_cycles[metric_frame]+1;
        if(dut.bank_core.engine.buffer_valid&&!dut.bank_core.engine.writer_input_ready)
            writer_blocked_cycles[metric_frame]=writer_blocked_cycles[metric_frame]+1;
        if(dut.bank_core.engine.core.sampler.cache.inner.state==2&&!dut.bank_core.engine.arready)
            cache_ar_wait_cycles[metric_frame]=cache_ar_wait_cycles[metric_frame]+1;
        if(dut.bank_core.engine.core.sampler.cache.inner.state==3&&!dut.bank_core.engine.rvalid)
            cache_r_wait_cycles[metric_frame]=cache_r_wait_cycles[metric_frame]+1;
    end

    reg first_w;reg [63:0] stamp,period;
    integer scan_current=-1,scan_count=0,scan_sequence=0,all_scanned_pixels=0,normal_scanned_pixels=0,blank_de_pixels=0,pf;
    integer output_tick=0,frame_origin_tick=0,out_x=0,out_y=0,scan_start_tick=0,blank_output_rasters=0;
    reg raster_seen=0,previous_out_vs=0,raster_had_pixels=0;
    reg [31:0] scan_crc=32'hffffffff;reg done_seen=0;
    reg [23:0] expected_rgb;reg [15:0] actual_word;
    integer abort_scan_pixels=0,abort_guard=0;
    reg fault_isolation_passed=0,release_edge_fault_isolated=0,common_reset_recovered=0,normal_phase_completed=0;
    integer normal_captured=0,normal_processed=0,normal_presented=0,normal_good=0,normal_repeat=0,normal_blank=0;
    integer normal_drop=0,normal_overflow=0,normal_no_free=0,normal_underflow=0,normal_mismatch=0;
    integer normal_unique=0,normal_pixels=0,normal_source_beats=0,normal_result_beats=0;

    function automatic integer texture(input integer frame);
        texture=(frame+(phase_id==2 ? 2:0))%3;
    endfunction
    function automatic [255:0] oracle_word(input integer frame,input integer offset,input integer kind);
        oracle_word=kind==0 ? source_words[texture(frame)*FB+offset]:result_words[texture(frame)*FB+offset];
    endfunction
    function automatic [23:0] expand565(input [15:0] p);
        expand565={p[15:11],p[15:13],p[10:5],p[10:9],p[4:0],p[4:2]};
    endfunction
    function automatic [31:0] crc_byte(input [31:0] old,input [7:0] b);
        reg [31:0] c;integer bitno;begin
            c=old^b;for(bitno=0;bitno<8;bitno=bitno+1)c=c[0] ? (c>>1)^32'hedb88320:c>>1;crc_byte=c;
        end
    endfunction
    task automatic log_event(input [8*28-1:0] kind,input integer frame,input integer b,input [63:0] when_ps);
        begin $fdisplay(events,"%0s,%0d,%0d,%0d,%0d",kind,phase_id,frame+1,b,when_ps);$fflush(events);end
    endtask
    task automatic clear_scoreboard;
        begin
            source_window_closed=0;tx_frame=-1;previous_in_vs=0;
            commit_total=0;release_total=0;publish_total=0;unique_total=0;
            total_source_beats=0;total_result_beats=0;total_readback_beats=0;
            for(i=0;i<2;i=i+1)begin source_epoch[i]=-1;result_epoch[i]=-1;end
            for(i=0;i<8;i=i+1)begin
                source_bank_for[i]=-1;result_bank_for[i]=-1;input_pixels[i]=0;source_written[i]=0;result_written[i]=0;readback_beats[i]=0;
                commits[i]=0;releases[i]=0;publications[i]=0;unique_scans[i]=0;scan_pixels[i]=0;
                observed_source_crc[i]=0;observed_scan_crc[i]=0;
                begins[i]=0;fills[i]=0;scatter_cycles[i]=0;process_cycles[i]=0;future_capture_overlap[i]=0;
                coordinates_issued[i]=0;scan_active_cycles[i]=0;coordinate_blocked_cycles[i]=0;tail_drain_cycles[i]=0;
                writer_blocked_cycles[i]=0;cache_ar_wait_cycles[i]=0;cache_r_wait_cycles[i]=0;
                first_ps[i]=0;last_ps[i]=0;commit_ps[i]=0;release_ps[i]=0;publish_ps[i]=0;
                scan_start_ps[i]=0;scan_last_ps[i]=0;scan_done_ps[i]=0;sof_ps[i]=0;
            end
            sof_ps[8]=0;scan_current=-1;scan_count=0;scan_crc=32'hffffffff;done_seen=0;
        end
    endtask
    task automatic reset_domains(input integer next_phase);
        begin
            // Keep the old phase/fault interpretation until common reset is
            // actually asserted. Otherwise an intervening core posedge can
            // see the deliberately sticky E1 as a recovery-phase failure.
            @(negedge core_clk);rst_n=0;phase_id=next_phase;
            capture_admit=0;scan_enable=0;external_fault=0;external_fault_code=0;
            raw_de=0;raw_vs=0;raw_hs=0;raw_rgb=0;
            repeat(12)@(negedge core_clk);clear_scoreboard();
            if(SMALL && next_phase==0)begin
                // Exercise only the corrected local-reset aperture. The DDR
                // behavior model itself remains unchanged: force this DUT
                // input, then remove it before the first active local edge.
                force dut.input_link.shared_writes.wready=1'b1;
                rst_n=1;
                repeat(2)begin
                    @(posedge core_clk);
                    if(dut.cr!==1'b0 || dut.input_link.core_rst_n!==1'b0)
                        $fatal(1,"C reset release was active during its first two sampled core edges");
                    #1;
                    if(dut.input_link.contract_failed!==0 || dut.input_link.shared_writes.state!==0 ||
                        dut.input_link.shared_writes.owner!==0 || dut.input_link.shared_writes.last_owner!==1 ||
                        dut.input_link.shared_writes.address!==0 || dut.input_link.shared_writes.length!==0 ||
                        dut.input_link.shared_writes.beat!==0 || dut.input_link.shared_writes.watchdog!==0 ||
                        dut.input_link.shared_writes.failed!==0 || dut.input_link.shared_writes.fault!==0 ||
                        dut.input_link.shared_writes.bursts0!==0 || dut.input_link.shared_writes.bursts1!==0)
                        $fatal(1,"C local reset did not dominate all arbiter/contract state with WREADY=1");
                end
                @(negedge core_clk);release dut.input_link.shared_writes.wready;
                #1;
                if(dut.cr!==1'b1)$fatal(1,"C two-stage release did not activate after two core edges");
                $display("PASS C_LOCAL_RESET_PROBE sampled_reset_edges=2 forced_wready=1 core_clock_paused=0");
            end else rst_n=1;
            repeat(12)@(negedge core_clk);capture_admit=1;scan_enable=1;
        end
    endtask
    task automatic send_frames(input integer count);
        integer frame,x,y;begin
            @(negedge pix_in_clk);
            for(frame=0;frame<count;frame=frame+1)begin
                tx_frame=frame;
                for(y=0;y<SIM_VT;y=y+1)for(x=0;x<SIM_HT;x=x+1)begin
                    raw_vs=y<SIM_VS;raw_hs=x<SIM_HS;
                    raw_de=y>=SIM_Y0&&y<SIM_Y0+H&&x>=SIM_X0&&x<SIM_X0+W;
                    raw_rgb=raw_de ? (expand565(sources[texture(frame)*N+(y-SIM_Y0)*W+x-SIM_X0]) ^ ((24'h010101*(x+y+frame))&24'h070307)):0;
                    @(negedge pix_in_clk);
                end
            end
            tx_frame=count;raw_vs=1;raw_hs=0;raw_de=0;raw_rgb=0;
            @(posedge pix_in_clk);@(negedge pix_in_clk);capture_admit=0;source_window_closed=1;
        end
    endtask
    always @(posedge pix_in_clk)begin
        if(!rst_n)previous_in_vs=0;
        else begin
            if(pix_in_vsync_active&&!previous_in_vs)begin
                if(tx_frame<0||tx_frame>8)$fatal(1,"input SOF outside declared unthrottled sequence");
                sof_ps[tx_frame]=$time;
                if(tx_frame==8)log_event("input_terminal_eof",7,-1,$time);else log_event("input_sof",tx_frame,-1,$time);
                if(tx_frame>0)begin
                    period=sof_ps[tx_frame]-sof_ps[tx_frame-1];
                    if(period!=PERIOD_PS&&period!=PERIOD_PS+1)$fatal(1,"input raster cadence waited/changed");
                end
            end
            previous_in_vs=pix_in_vsync_active;
            if(pix_in_de)begin
                if(tx_frame<0||tx_frame>=8||input_pixels[tx_frame]>=N)$fatal(1,"extra input DE pixel");
                if(input_pixels[tx_frame]==0)begin first_ps[tx_frame]=$time;log_event("input_first",tx_frame,-1,$time);end
                input_pixels[tx_frame]=input_pixels[tx_frame]+1;last_ps[tx_frame]=$time;
                if(input_pixels[tx_frame]==N)log_event("input_last",tx_frame,-1,$time);
            end
        end
    end
    always @(negedge core_clk)begin
        ticks=ticks+1;
        if(ticks>SIM_MAX_CYCLES)$fatal(1,"bounded system simulation exceeded system cycles; retain all partial rows");
        if(rst_n&&ticks%1000000==0)$display("SYSTEM_PROGRESS phase=%0d ticks=%0d inputID=%0d commits=%0d releases=%0d unique=%0d fifo=%0d/%0d failed=%0d",phase_id,ticks,tx_frame+1,commit_total,release_total,unique_total,fifo_used,fifo_available,failed);
        arready=rst_n&&rleft==0&&ticks%7>=2;
        rvalid=rst_n&&rleft!=0&&ticks%5!=0;rlast=rleft==1;rid=0;
        if(rvalid)rdata=memory[rindex];
        // Require a complete stalled cycle on every newly presented AW;
        // periodic phase coincidence must not erase backpressure coverage.
        awready=rst_n&&wleft==0&&ticks%9>=3&&c_aw_seen_valid;
        c_aw_seen_valid=rst_n&&awvalid;
        wready=rst_n&&(wleft!=0||(awvalid&&awready&&ticks%2==0))&&ticks%6!=0;
        wlast=wleft==1;
    end
    always @(posedge core_clk)begin
        if(!rst_n)begin
            rleft<=0;wleft<=0;heldar<=0;heldaw<=0;heldw<=0;heldresult<=0;
            previous_release=0;previous_publish=0;previous_commit=0;cache_lines_seen=0;live_cache_lines=0;
        end else begin
            if(failed&&phase_id!=1)$fatal(1,"unexpected system failure phase=%0d fault=%h",phase_id,fault);
            if(heldar&&(!arvalid||araddr!==saved_ar||arlen!==saved_arlen))$fatal(1,"physical AR changed while stalled");
            if(heldaw&&(!awvalid||awaddr!==saved_aw||awlen!==saved_awlen))$fatal(1,"physical AW changed while stalled");
            if(heldw&&wdata!==saved_w)$fatal(1,"physical W changed while stalled");
            if(heldresult&&(!dut.bank_core.engine.result_valid||{dut.bank_core.engine.result_rgb[23:19],dut.bank_core.engine.result_rgb[15:10],dut.bank_core.engine.result_rgb[7:3]}!==saved_result565||dut.bank_core.engine.result_tag!==saved_tag))$fatal(1,"Sampled output/tag changed while stalled");
            heldar<=arvalid&&!arready;saved_ar<=araddr;saved_arlen<=arlen;
            heldaw<=awvalid&&!awready;saved_aw<=awaddr;saved_awlen<=awlen;
            heldw<=wleft!=0&&!wready;saved_w<=wdata;
            heldresult<=dut.bank_core.engine.result_valid&&!dut.bank_core.engine.result_ready;
            saved_result565<={dut.bank_core.engine.result_rgb[23:19],dut.bank_core.engine.result_rgb[15:10],dut.bank_core.engine.result_rgb[7:3]};saved_tag<=dut.bank_core.engine.result_tag;
            if(phase_id==0)begin
                if(arvalid&&!arready)physical_ar_stall=physical_ar_stall+1;
                if(awvalid&&!awready)aw_stall=aw_stall+1;
                if(wleft!=0&&!wready)w_stall=w_stall+1;
                if(dut.bank_core.engine.result_valid&&!dut.bank_core.engine.result_ready)writer_input_stall=writer_input_stall+1;
                if(dut.bank_core.engine.result_valid&&!dut.bank_core.engine.result_ready)core_output_stall=core_output_stall+1;
                if(dut.bank_core.engine.core.sampler.cache.out_valid&&!dut.bank_core.engine.core.sampler.cache.out_ready)cache_output_stall=cache_output_stall+1;
                if(dut.input_link.dma_awvalid&&dut.input_link.core_awvalid)write_contention=write_contention+1;
                if(dut.reader.arvalid&&dut.bank_core.arvalid)read_contention=read_contention+1;
                if(dut.input_link.input_dma.capture.unused_used>peak_input_fifo)peak_input_fifo=dut.input_link.input_dma.capture.unused_used;
                if(fifo_used>peak_output_fifo)peak_output_fifo=fifo_used;
            end
            if(dut.input_link.input_dma.grant_valid&&dut.input_link.input_dma.grant_ready)begin
                f=dut.input_link.input_dma.next_id-1;bank=dut.input_link.input_dma.grant_bank;
                if(f<0||f>=8||capture_reserved[bank]||source_epoch[bank]>=0&&releases[source_epoch[bank]]!=1)$fatal(1,"input bank reservation reused an unreleased source");
                source_epoch[bank]=f;source_bank_for[f]=bank;log_event("source_reserved",f,bank,$time);
            end
            if(processing)begin
                f=dut.bank_core.accepted_id-1;
                if(f<0||f>=8||source_epoch[dut.bank_core.active_source]!=f||!capture_reserved[dut.bank_core.active_source])$fatal(1,"processing unowned source epoch");
                if(dut.bank_core.engine.core.sampler.cache.inner.state==4)scatter_cycles[f]=scatter_cycles[f]+1;
                if(dut.bank_core.engine.result_valid&&dut.bank_core.engine.result_ready)begin
                    if(dut.bank_core.engine.result_tag>=N||dut.bank_core.engine.result_masked!==masks[texture(f)*N+dut.bank_core.engine.result_tag])$fatal(1,"CPU independent geometry mask mismatch");
                end
                if(dut.bank_core.engine.core.sampler.cache.inner.scatter_write&&dut.bank_core.engine.core.sampler.cache.inner.scatter_group==7)begin
                    k=dut.bank_core.engine.core.sampler.cache.inner.selected_line;
                    if(!cache_lines_seen[k])begin cache_lines_seen[k]=1;live_cache_lines=live_cache_lines+1;end
                    if(phase_id==0&&live_cache_lines>peak_cache_lines)peak_cache_lines=live_cache_lines;
                end
            end
            if(arvalid&&arready)begin
                bank=araddr/STRIDE;off=araddr%STRIDE;
                if(rleft!=0||bank>3||off%8||off+(arlen+1)*8>FU)$fatal(1,"physical AR outside frame region");
                if(arlen==7)begin
                    f=source_epoch[bank];
                    if(bank>1||f<0||!processing||bank!=dut.bank_core.active_source||source_written[f]!=FB||off%64)$fatal(1,"source AR ownership/epoch violation");
                end else if(arlen==15)begin
                    f=result_epoch[bank-2];
                    if(bank<2||f<0||!display_active||bank!=2+front_bank||result_written[f]!=FB||off%128)$fatal(1,"display AR ownership/epoch violation");
                end else $fatal(1,"unexpected AR burst length");
                rleft<=arlen+1;rindex<=bank*FB+(off>>3);rbank<=bank;rframe<=f;
            end
            if(rvalid)begin
                if(rframe<0||rdata!==oracle_word(rframe,rindex-rbank*FB,rbank<2?0:1))$fatal(1,"physical R stale/corrupt epoch");
                if(rbank>=2)begin readback_beats[rframe]=readback_beats[rframe]+1;total_readback_beats=total_readback_beats+1;end
                rleft<=rleft-1;rindex<=rindex+1;
            end
            if(awvalid&&awready)begin
                bank=awaddr/STRIDE;off=awaddr%STRIDE;
                if(wleft!=0||awlen!=15||bank>3||off%128||off+128>FU)$fatal(1,"physical AW layout/length overlap");
                if(bank<2)begin
                    f=source_epoch[bank];
                    if(f<0||!capture_reserved[bank]||(processing&&dut.bank_core.active_source==bank))$fatal(1,"capture writes locked source");
                end else begin
                    f=dut.bank_core.accepted_id-1;
                    if(f<0||f>=8||!processing||bank!=2+write_bank||(display_active&&write_bank==front_bank))$fatal(1,"result writes locked/wrong bank");
                    if(result_epoch[bank-2]!=f)begin
                        if(off!=0||result_written[f]!=0||(result_epoch[bank-2]>=0&&unique_scans[result_epoch[bank-2]]==0))$fatal(1,"result bank reused before actual prior scan");
                        result_epoch[bank-2]=f;result_bank_for[f]=bank;
                    end
                end
                wleft<=16;windex<=bank*FB+(off>>3);wbank<=bank;wframe<=f;
            end
            if(wready)begin
                first_w=wleft==0&&awvalid&&awready;tb=first_w?bank:wbank;tf=first_w?f:wframe;
                ti=first_w?bank*FB+(off>>3):windex;to=ti-tb*FB;
                if(wleft==0&&!first_w||tf<0||tf>=8||wstrb!==32'hffffffff||wlast!=(!first_w&&wleft==1))$fatal(1,"physical W owner/strobe/last mismatch");
                if(wdata!==oracle_word(tf,to,tb<2?0:1))$fatal(1,"actual DMA/result W differs from independent CPU pixels ID=%0d bank=%0d beat=%0d",tf+1,tb,to);
                if(tb<2)begin
                    source_written[tf]=source_written[tf]+1;total_source_beats=total_source_beats+1;
                    if(phase_id==0&&scan_current>=2&&scan_current<=5&&tf>scan_current)future_capture_overlap[scan_current]=future_capture_overlap[scan_current]+1;
                end else begin result_written[tf]=result_written[tf]+1;total_result_beats=total_result_beats+1;end
                memory[ti]<=wdata;wleft<=first_w?15:wleft-1;windex<=ti+1;
            end
            if(rleft!=0&&wleft!=0&&rbank==wbank)$fatal(1,"physical R/W simultaneously own one bank");
            #1;stamp=$time-1;
            if(source_commit&&!previous_commit)begin
                f=source_commit_id-1;
                if(f<0||f>=8||commits[f]!=0||f!=commit_total||source_pixels!=N||source_crc!==source_crcs[texture(f)]||source_written[f]!=FB||input_pixels[f]!=N||source_epoch[source_commit_bank]!=f)$fatal(1,"input commit ID/actual DMA/source CRC/count mismatch");
                commits[f]=1;commit_total=commit_total+1;commit_ps[f]=stamp;begins[f]=cache_misses;observed_source_crc[f]=source_crc;
                cache_lines_seen=0;live_cache_lines=0;log_event("source_commit",f,source_commit_bank,stamp);
            end
            if(source_release&&!previous_release)begin
                f=source_release_id-1;
                if(f<0||f>=8||releases[f]!=0||commits[f]!=1||source_epoch[released_bank]!=f||result_written[f]!=FB||
                   (rleft!=0&&rbank==released_bank)||dut.bank_core.arvalid||dut.bank_core.awvalid||
                   (wleft!=0&&wbank==2+write_bank))$fatal(1,"source release before actual source/result drain");
                if(scatter_cycles[f]!=8*(cache_misses-begins[f]))$fatal(1,"scatter16 fill8 count mismatch");
                releases[f]=1;release_total=release_total+1;release_ps[f]=stamp;fills[f]=cache_misses-begins[f];process_cycles[f]=last_process_cycles;
                log_event("source_release",f,released_bank,stamp);
            end
            if(result_publish&&!previous_publish)begin
                f=publish_id-1;
                if(f<0||f>=8||publications[f]!=0||result_epoch[publish_bank-2]!=f)$fatal(1,"wrong/duplicate result publication");
                publications[f]=1;publish_total=publish_total+1;publish_ps[f]=stamp;log_event("result_publish",f,publish_bank,stamp);
            end
            previous_commit=source_commit;previous_release=source_release;previous_publish=result_publish;
        end
    end

    // Observe actual registered pixel outputs, not FIFO-write or reader.done.
    always @(posedge pix_out_clk)begin
        if(!rst_n)begin
            scan_current=-1;scan_count=0;scan_crc=32'hffffffff;done_seen=0;abort_guard=0;
            output_tick=0;frame_origin_tick=0;raster_seen=0;previous_out_vs=0;raster_had_pixels=0;
        end
        else begin
            #1;output_tick=output_tick+1;
            if(pix_vs&&!previous_out_vs)begin
                if(raster_seen)begin
                    if(output_tick-frame_origin_tick!=SIM_HT*SIM_VT)$fatal(1,"actual output raster period changed");
                    if(!raster_had_pixels&&phase_id==0)blank_output_rasters=blank_output_rasters+1;
                end
                frame_origin_tick=output_tick;raster_seen=1;raster_had_pixels=0;
            end
            previous_out_vs=pix_vs;
            if(raster_seen)begin
                out_x=(output_tick-frame_origin_tick)%SIM_HT;out_y=((output_tick-frame_origin_tick)/SIM_HT)%SIM_VT;
                if(pix_hs!==(out_x<SIM_HS)||pix_vs!==(out_y<SIM_VS)||pix_de!==(out_x>=SIM_X0&&out_x<SIM_X0+W&&out_y>=SIM_Y0&&out_y<SIM_Y0+H))
                    $fatal(1,"actual registered HS/VS/DE raster differs x=%0d y=%0d",out_x,out_y);
            end
            if(phase_id==1&&external_fault)abort_guard=abort_guard+1;
            if(pix_pixel_valid)begin
                if(!pix_de)$fatal(1,"scanner claims a pixel outside actual DE");
                pf=pix_frame_id-1;
                if(pf<0||pf>=8||result_epoch[pix_frame_bank]!=pf)$fatal(1,"actual scanner ID/bank epoch differs");
                if(pix_frame_start)begin
                    if(scan_current!=-1)$fatal(1,"overlapping actual scans");
                    scan_current=pf;scan_count=0;scan_crc=32'hffffffff;scan_start_tick=output_tick;
                    if(!raster_seen||out_x!=SIM_X0||out_y!=SIM_Y0)$fatal(1,"actual scan began outside native ROI");
                    if(unique_scans[pf]==0)scan_start_ps[pf]=$time-1;
                    log_event("scan_start",pf,2+pix_frame_bank,$time-1);
                end
                if(scan_current!=pf||scan_count>=N)$fatal(1,"actual scan tag/order/count differs");
                if(output_tick-scan_start_tick!=(scan_count/W)*SIM_HT+scan_count%W)$fatal(1,"actual valid-pixel/line cadence changed");
                raster_had_pixels=1;
                expected_rgb=expand565(goldens[texture(pf)*N+scan_count]);
                if(pix_rgb!==expected_rgb)$fatal(1,"actual DE/RGB pixel differs ID=%0d pixel=%0d got=%h expected=%h",pf+1,scan_count,pix_rgb,expected_rgb);
                actual_word={pix_rgb[23:19],pix_rgb[15:10],pix_rgb[7:3]};
                scan_crc=crc_byte(crc_byte(scan_crc,actual_word[7:0]),actual_word[15:8]);
                scan_count=scan_count+1;all_scanned_pixels=all_scanned_pixels+1;
                if(phase_id==0)normal_scanned_pixels=normal_scanned_pixels+1;
                if(pix_frame_last)begin
                    if(scan_count!=N||~scan_crc!==result_crcs[texture(pf)])$fatal(1,"actual last pixel count/independent CRC mismatch");
                    if(unique_scans[pf]==0)scan_last_ps[pf]=$time-1;
                    log_event("scan_last_pixel",pf,2+pix_frame_bank,$time-1);
                    scan_current=-1;
                end
            end else begin
                if(pix_rgb!==24'h0)$fatal(1,"blank/inactive/fault output is not black");
                if(pix_de&&phase_id==0)blank_de_pixels=blank_de_pixels+1;
            end
            if(pix_done_toggle!=done_seen)begin
                done_seen=pix_done_toggle;pf=pix_frame_id-1;
                if(pix_done_good)begin
                    if(pf<0||pf>=8||scan_count!=N||pix_done_crc!==result_crcs[texture(pf)]||~scan_crc!==pix_done_crc)$fatal(1,"good done is not supported by actual DE/RGB scan");
                    if(unique_scans[pf]==0)begin
                        if(pf!=unique_total)$fatal(1,"new actual scan skipped/reordered an ID");
                        unique_scans[pf]=1;unique_total=unique_total+1;scan_pixels[pf]=N;scan_done_ps[pf]=$time-1;observed_scan_crc[pf]=pix_done_crc;
                    end
                    $fdisplay(scans_csv,"%0d,%0d,%0d,%0d,%0d,%0d,%08x,%0d",phase_id,pf+1,2+pix_frame_bank,scan_sequence,scan_count,$time-1,pix_done_crc,unique_total);
                    $fflush(scans_csv);scan_sequence=scan_sequence+1;log_event("scan_done_good",pf,2+pix_frame_bank,$time-1);
                end else if(phase_id!=1)$fatal(1,"bad scan completion outside deliberate small fault phase");
            end
            if(phase_id==1&&abort_guard>8&&(pix_pixel_valid||pix_rgb!==0))$fatal(1,"faulted scanner continued exposing new valid pixels");
        end
    end
    integer key_toggles=0,frame_mode_latches=0,mode_changes_while_processing=0;
    reg tracked_processing=0,locked_mode=1;
    always @(posedge core_clk)if(rst_n)begin
        if(toggle_pulse)begin
            key_toggles=key_toggles+1;
            if(processing)mode_changes_while_processing=mode_changes_while_processing+1;
        end
        if(dut.bank_core.engine.begin_frame)begin
            if(dut.bank_core.active_corrected!==(dut.bank_core.accepted_id==1))
                $fatal(1,"new frame accepted incorrect requested mode");
            frame_mode_latches=frame_mode_latches+1;
        end
        if(processing&&!tracked_processing)locked_mode=dut.bank_core.active_corrected;
        if(processing&&tracked_processing&&dut.bank_core.active_corrected!==locked_mode)
            $fatal(1,"KEY changed mode of active bank transaction");
        tracked_processing=processing;
    end
    task automatic key_level(input reg level,input integer count);
        begin @(negedge core_clk);key1_n=level;repeat(count)@(negedge core_clk);end
    endtask
    initial begin
        wait(rst_n);
        wait(dut.bank_core.engine.state==1&&dut.bank_core.engine.index>8);
        // Sub-debounce contact bounce must not change the requested mode.
        key_level(0,1);key_level(1,10);
        if(corrected_requested!==1)$fatal(1,"short contact bounce toggled view");
        // Three complete presses while the corrected frame is in flight.
        // The final requested identity applies only to the next frame.
        key_level(0,12);key_level(1,12);
        key_level(0,12);key_level(1,12);
        key_level(0,24);key_level(1,12);
        if(corrected_requested!==0||key_toggles!=3)$fatal(1,"rapid press/release/held-key contract failed");
    end
    task automatic wait_drain;
        integer limit;begin
            limit=0;
            while((processing||pending||display_active||capture_reserved!=0||read_busy||write_busy||rleft!=0||wleft!=0||arvalid||awvalid||fifo_used!=0||fifo_available!=0||dut.output_video.frame_active||!dut.reader.idle||dut.input_link.input_dma.active||!dut.input_link.input_dma.capture.fifo_idle||dut.input_link.input_dma.crc_busy||dut.bank_core.source_writable!==2'b11||dut.output_video.done_pending||dut.response_busy||dut.awaiting_bank_grant||dut.display_req_valid)&&limit<500000)begin
                @(negedge core_clk);limit=limit+1;
            end
            repeat(40)@(negedge core_clk);
            if(processing||pending||display_active||capture_reserved!=0||read_busy||write_busy||rleft!=0||wleft!=0||arvalid||awvalid||fifo_used!=0||fifo_available!=0||dut.output_video.frame_active||dut.display_fifo.rd_valid||!dut.reader.idle||dut.input_link.input_dma.active||!dut.input_link.input_dma.capture.fifo_idle||dut.input_link.input_dma.crc_busy||dut.bank_core.source_writable!==2'b11||dut.output_video.done_pending||dut.output_video.queued!=0||dut.output_video.inflight!=0||dut.response_busy||dut.awaiting_bank_grant||dut.display_req_valid)
                $fatal(1,"system source/result/FIFO/arb/reader/scan ownership did not drain");
        end
    endtask
    initial begin
        if(SIM_FRAMES!=2||W%16||H%8||N%256||SIM_HT<SIM_X0+W||SIM_VT<=SIM_Y0+H)$fatal(1,"invalid two-frame geometry");
        if(NATIVE&&(SIM_HT!=2200||SIM_VT!=1125||SIM_X0!=192||SIM_Y0!=41||SIM_HS!=44||SIM_VS!=5))$fatal(1,"native raster differs from1920x1080");
        $readmemh("source0.mem",sources,0,N-1);$readmemh("source1.mem",sources,N,2*N-1);$readmemh("source2.mem",sources,2*N,3*N-1);
        $readmemh("expected0.mem",goldens,0,N-1);$readmemh("expected1.mem",goldens,N,2*N-1);$readmemh("expected2.mem",goldens,2*N,3*N-1);
        $readmemh("masks0.mem",masks,0,N-1);$readmemh("masks1.mem",masks,N,2*N-1);$readmemh("masks2.mem",masks,2*N,3*N-1);
        $readmemh("sourcecrc0.mem",source_crcs,0,0);$readmemh("sourcecrc1.mem",source_crcs,1,1);$readmemh("sourcecrc2.mem",source_crcs,2,2);
        $readmemh("crc0.mem",result_crcs,0,0);$readmemh("crc1.mem",result_crcs,1,1);$readmemh("crc2.mem",result_crcs,2,2);
        for(i=0;i<3*N;i=i+1)begin source_words[i/16][(i%16)*16+:16]=sources[i];result_words[i/16][(i%16)*16+:16]=goldens[i];end
        events=$fopen("events.csv","w");frames_csv=$fopen("frames.csv","w");scans_csv=$fopen("scans.csv","w");
        $fdisplay(events,"event,phase,frame_id,physical_bank,time_ps");
        $fdisplay(frames_csv,"frame_id,source_bank,result_bank,input_pixels,source_beats,result_beats,commits,releases,publishes,unique_scans,input_first_ps,input_last_ps,commit_ps,source_release_ps,publish_ps,scan_start_ps,scan_last_pixel_ps,scan_done_ps,fills,scatter_cycles,hardware_process_cycles,future_capture_write_overlap_cycles,source_crc32,scan_crc32");
        $fdisplay(scans_csv,"phase,frame_id,physical_bank,scan_index,scanned_pixels,done_ps,crc32,unique_total");
        clear_scoreboard();reset_domains(0);send_frames(SIM_FRAMES);
        wait(unique_total==SIM_FRAMES);@(negedge core_clk);scan_enable=0;wait_drain();
        if(captured_frames!=SIM_FRAMES||processed_frames!=SIM_FRAMES||presented_frames!=SIM_FRAMES||
           commit_total!=SIM_FRAMES||release_total!=SIM_FRAMES||publish_total!=SIM_FRAMES||unique_total!=SIM_FRAMES||
           total_source_beats!=SIM_FRAMES*FB||total_result_beats!=SIM_FRAMES*FB||queries!=SIM_FRAMES*N||
           underflows!=0||mismatches!=0||dut.input_link.dropped_frames!=0||dut.input_link.overflow_frames!=0||dut.input_link.no_free_frames!=0)
            $fatal(1,"two input/source/process/actual scan/drop contract failed");
        for(i=0;i<SIM_FRAMES;i=i+1)begin
            if(input_pixels[i]!=N||source_written[i]!=FB||result_written[i]!=FB||commits[i]!=1||releases[i]!=1||
               publications[i]!=1||unique_scans[i]!=1||scan_pixels[i]!=N||source_bank_for[i]!=i%2)
                $fatal(1,"two-frame per-ID counts failed ID=%0d",i+1);
            $fdisplay(frames_csv,"%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%08x,%08x",i+1,source_bank_for[i],result_bank_for[i],input_pixels[i],source_written[i],result_written[i],commits[i],releases[i],publications[i],unique_scans[i],first_ps[i],last_ps[i],commit_ps[i],release_ps[i],publish_ps[i],scan_start_ps[i],scan_last_ps[i],scan_done_ps[i],fills[i],scatter_cycles[i],process_cycles[i],future_capture_overlap[i],observed_source_crc[i],observed_scan_crc[i]);
        end
        if(key_toggles!=3||mode_changes_while_processing!=3||frame_mode_latches!=SIM_FRAMES)
            $fatal(1,"mode change/active-frame lock coverage missing");
        performance_csv=$fopen("performance.csv","w");
        $fdisplay(performance_csv,"frame_id,corrected,coordinates_issued,scan_active_cycles,coordinate_blocked_cycles,tail_drain_cycles,writer_blocked_cycles,cache_ar_wait_cycles,cache_r_wait_cycles,cache_fills,scatter_cycles,hardware_process_cycles");
        for(i=0;i<SIM_FRAMES;i=i+1)begin
            if(coordinates_issued[i]!=N||scan_active_cycles[i]!=N+coordinate_blocked_cycles[i])
                $fatal(1,"coordinate cycle breakdown incomplete");
            $fdisplay(performance_csv,"%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d",i+1,i==0,coordinates_issued[i],scan_active_cycles[i],coordinate_blocked_cycles[i],tail_drain_cycles[i],writer_blocked_cycles[i],cache_ar_wait_cycles[i],cache_r_wait_cycles[i],fills[i],scatter_cycles[i],process_cycles[i]);
        end
        $fclose(performance_csv);
        $fflush(frames_csv);
        summary=$fopen("summary.json","w");
        $fdisplay(summary,"{\"passed\":true,\"frames_input\":%0d,\"frames_committed\":%0d,\"frames_processed\":%0d,\"frames_published\":%0d,\"frames_unique_scanned\":%0d,\"unique_scanned_pixels\":%0d,\"all_scanned_pixels\":%0d,\"source_beats\":%0d,\"result_beats\":%0d,\"output_underflows\":%0d,\"output_crc_mismatches\":%0d,\"aw_stall\":%0d,\"w_stall\":%0d,\"physical_ar_stall\":%0d,\"cache_output_stall\":%0d,\"core_output_stall\":%0d,\"writer_input_stall\":%0d,\"write_contention\":%0d,\"read_contention\":%0d,\"dropped_frames\":%0d,\"overflow_frames\":%0d,\"no_free_frames\":%0d,\"key_toggles\":%0d,\"mode_changes_while_processing\":%0d,\"frame_mode_latches\":%0d,\"final_drain\":true,\"fault_injection_exercised\":false,\"whole_frame_drop_exercised\":false}",SIM_FRAMES,captured_frames,processed_frames,publish_total,unique_total,SIM_FRAMES*N,all_scanned_pixels,total_source_beats,total_result_beats,underflows,mismatches,aw_stall,w_stall,physical_ar_stall,cache_output_stall,core_output_stall,writer_input_stall,write_contention,read_contention,dut.input_link.dropped_frames,dut.input_link.overflow_frames,dut.input_link.no_free_frames,key_toggles,mode_changes_while_processing,frame_mode_latches);
        $fclose(summary);$fclose(frames_csv);$fclose(scans_csv);$fclose(events);
        $display("PASS hdmi_camera_fisheye_tile8_system: %0dx%0d two raw148.5 input frames, real sampler/DMA/DDR/fisheye+identity/FIFO/pixel74.25 scan and full drain; no PHY/hardware claim",W,H);
        $finish;
    end
endmodule
