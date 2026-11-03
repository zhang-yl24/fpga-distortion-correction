`timescale 1ps/1ps
// Normalized digital input -> actual DMA -> correction -> actual async FIFO ->
// registered DE/RGB scan. Modeled DDR UI only; never a physical PHY test.
module tb_penn_system;
    `include "config.vh"
    `include "timing.vh"
    localparam W=VEC_WIDTH,H=VEC_HEIGHT,N=W*H,FB=N/16,FU=N/2,STRIDE=1048576;
    localparam NATIVE=W==1920&&H==1080,SMALL=W==32&&H==32;
    localparam [63:0] PERIOD_PS=(64'd4000000*SIM_HT*SIM_VT)/297;
    reg core_clk=0,pix_in_clk=0,pix_out_clk=0;
    always #4000 core_clk=~core_clk;
    integer in_phase=0,in_delay,out_phase=0,out_delay;
    initial forever begin
        in_phase=in_phase+2000000;in_delay=in_phase/297;in_phase=in_phase%297;
        #(in_delay)pix_in_clk=~pix_in_clk;
    end
    initial begin
        #(SIM_OUTPUT_PHASE_PS);
        forever begin
            out_phase=out_phase+2000000;out_delay=out_phase/297;out_phase=out_phase%297;
            #(out_delay)pix_out_clk=~pix_out_clk;
        end
    end
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
    reg gamma_enable=0,correction_enable=0;
    reg signed [23:0] rot_cx=VEC_OUT_CX,rot_cy=VEC_OUT_CY;
    reg signed [31:0] rot_cos=32'sd1073741824,rot_sin=0;
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
    hdmi1080_video_system_geometry_ab #(.WIDTH(W),.HEIGHT(H),.BANK_STRIDE(STRIDE),.MAX_RADIUS_Q22(VEC_RADIUS_GUARD_Q22),
        .HT(SIM_HT),.VT(SIM_VT),.HS(SIM_HS),.VS(SIM_VS),.X0(SIM_X0),.Y0(SIM_Y0)) dut(
        .core_clk(core_clk),.pix_in_clk(pix_in_clk),.pix_out_clk(pix_out_clk),.rst_n(rst_n),
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

    // Four logical frame regions, addressed by bank/offset, not preloaded.
    reg [255:0] memory[0:4*FB-1];
    reg [15:0] sources[0:2*N-1],goldens[0:2*N-1];reg masks[0:2*N-1];
    reg [255:0] source_words[0:2*FB-1],result_words[0:2*FB-1];
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
    integer aw_stall=0,w_stall=0,physical_ar_stall=0,cache_output_stall=0,core_output_stall=0,tone_stall=0;
    integer write_contention=0,read_contention=0,peak_input_fifo=0,peak_output_fifo=0,peak_cache_lines=0;
    // One bounded SMALL-only selected-address hold for each arbiter. These
    // coverage stalls never affect the native input/output or ready cadence.
    localparam FORCE_HOLD_LIMIT=20000;
    reg forced_result_aw_done=0,forced_display_ar_done=0;
    integer forced_result_aw_hold_cycles=0,forced_display_ar_hold_cycles=0;
    integer forced_write_dual_clients_seen=0,forced_read_dual_clients_seen=0;
    reg [127:0] cache_lines_seen=0;integer live_cache_lines=0;
    reg heldar=0,heldaw=0,heldw=0,heldtone=0;
    reg [27:0] saved_ar,saved_aw;reg [3:0] saved_arlen,saved_awlen;
    reg [255:0] saved_w;reg [15:0] saved_tone;reg [23:0] saved_tag;
    reg previous_release=0,previous_publish=0,previous_commit=0;
    integer events,frames_csv,scans_csv,summary,i,j,k,f,bank,off,tf,tb,ti,to;
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
        texture=1; // one exact-Penn corrected frame, source files remain identical
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
            pix_in_de=0;pix_in_vsync_active=0;pix_in_rgb=0;
            repeat(12)@(negedge core_clk);clear_scoreboard();rst_n=1;
            repeat(12)@(negedge core_clk);capture_admit=1;scan_enable=1;
        end
    endtask
    task automatic send_frames(input integer count);
        integer frame,x,y;begin
            @(negedge pix_in_clk);
            for(frame=0;frame<count;frame=frame+1)begin
                tx_frame=frame;
                for(y=0;y<SIM_VT;y=y+1)for(x=0;x<SIM_HT;x=x+1)begin
                    pix_in_vsync_active=y<SIM_VS;
                    pix_in_de=y>=SIM_Y0&&y<SIM_Y0+H&&x>=SIM_X0&&x<SIM_X0+W;
                    pix_in_rgb=pix_in_de ? expand565(sources[texture(frame)*N+(y-SIM_Y0)*W+x-SIM_X0]):0;
                    @(negedge pix_in_clk);
                end
            end
            tx_frame=count;pix_in_vsync_active=1;pix_in_de=0;pix_in_rgb=0;
            @(posedge pix_in_clk);@(negedge pix_in_clk);capture_admit=0;source_window_closed=1;
        end
    endtask
    always @(posedge pix_in_clk)begin
        if(!rst_n)previous_in_vs=0;
        else begin
            if(pix_in_vsync_active&&!previous_in_vs)begin
                if(tx_frame<0||tx_frame>SIM_FRAMES)$fatal(1,"input SOF outside declared unthrottled sequence");
                sof_ps[tx_frame]=$time;
                if(tx_frame==SIM_FRAMES)log_event("input_terminal_eof",SIM_FRAMES-1,-1,$time);else log_event("input_sof",tx_frame,-1,$time);
                if(tx_frame>0)begin
                    period=sof_ps[tx_frame]-sof_ps[tx_frame-1];
                    if(period!=PERIOD_PS&&period!=PERIOD_PS+1)$fatal(1,"input raster cadence waited/changed");
                end
            end
            previous_in_vs=pix_in_vsync_active;
            if(pix_in_de)begin
                if(tx_frame<0||tx_frame>=SIM_FRAMES||input_pixels[tx_frame]>=N)$fatal(1,"extra input DE pixel");
                if(input_pixels[tx_frame]==0)begin first_ps[tx_frame]=$time;log_event("input_first",tx_frame,-1,$time);end
                input_pixels[tx_frame]=input_pixels[tx_frame]+1;last_ps[tx_frame]=$time;
                if(input_pixels[tx_frame]==N)log_event("input_last",tx_frame,-1,$time);
            end
        end
    end
    always @(negedge core_clk)begin
        ticks=ticks+1;
        if(ticks>SIM_MAX_CYCLES)$fatal(1,"bounded system simulation exceeded system cycles; retain all partial rows");
        if(rst_n&&ticks%250000==0)$display("SYSTEM_PROGRESS phase=%0d ticks=%0d inputID=%0d commits=%0d releases=%0d unique=%0d fifo=%0d/%0d failed=%0d",phase_id,ticks,tx_frame+1,commit_total,release_total,unique_total,fifo_used,fifo_available,failed);
        arready=rst_n&&rleft==0&&ticks%7>=2;
        if(1'b0&&phase_id==0&&rst_n&&!forced_display_ar_done&&arvalid&&araddr>=2*STRIDE&&arlen==15)begin
            if(dut.read_bus.owner!==1'b0)$fatal(1,"SMALL held display address has wrong read arbiter owner");
            if(dut.bank_core.arvalid)begin
                forced_display_ar_done=1;forced_read_dual_clients_seen=forced_read_dual_clients_seen+1;
            end else begin
                arready=0;forced_display_ar_hold_cycles=forced_display_ar_hold_cycles+1;
                if(forced_display_ar_hold_cycles>=FORCE_HOLD_LIMIT)$fatal(1,"bounded SMALL display AR hold never observed sample AR");
            end
        end
        rvalid=rst_n&&rleft!=0&&ticks%5!=0;rlast=rleft==1;rid=0;
        if(rvalid)rdata=memory[rindex];
        awready=rst_n&&wleft==0&&ticks%9>=3;
        if(1'b0&&phase_id==0&&rst_n&&!forced_result_aw_done&&awvalid&&awaddr>=2*STRIDE)begin
            if(dut.input_link.dma_awvalid)begin
                forced_result_aw_done=1;forced_write_dual_clients_seen=forced_write_dual_clients_seen+1;
            end else begin
                awready=0;forced_result_aw_hold_cycles=forced_result_aw_hold_cycles+1;
                if(forced_result_aw_hold_cycles>=FORCE_HOLD_LIMIT)$fatal(1,"bounded SMALL selected result AW never observed capture AW");
            end
        end
        wready=rst_n&&(wleft!=0||(awvalid&&awready&&ticks%2==0))&&ticks%6!=0;
        wlast=wleft==1;
    end
    always @(posedge core_clk)begin
        if(!rst_n)begin
            rleft<=0;wleft<=0;heldar<=0;heldaw<=0;heldw<=0;heldtone<=0;
            previous_release=0;previous_publish=0;previous_commit=0;cache_lines_seen=0;live_cache_lines=0;
        end else begin
            if(failed&&phase_id!=1)$fatal(1,"unexpected system failure phase=%0d fault=%h",phase_id,fault);
            if(heldar&&(!arvalid||araddr!==saved_ar||arlen!==saved_arlen))$fatal(1,"physical AR changed while stalled");
            if(heldaw&&(!awvalid||awaddr!==saved_aw||awlen!==saved_awlen))$fatal(1,"physical AW changed while stalled");
            if(heldw&&wdata!==saved_w)$fatal(1,"physical W changed while stalled");
            if(heldtone&&(!dut.bank_core.engine.tone_valid||dut.bank_core.engine.tone_pixel!==saved_tone||dut.bank_core.engine.tone_tag!==saved_tag))$fatal(1,"Gamma output/tag changed while stalled");
            heldar<=arvalid&&!arready;saved_ar<=araddr;saved_arlen<=arlen;
            heldaw<=awvalid&&!awready;saved_aw<=awaddr;saved_awlen<=awlen;
            heldw<=wleft!=0&&!wready;saved_w<=wdata;
            heldtone<=dut.bank_core.engine.tone_valid&&!dut.bank_core.engine.tone_ready;
            saved_tone<=dut.bank_core.engine.tone_pixel;saved_tag<=dut.bank_core.engine.tone_tag;
            if(phase_id==0)begin
                if(arvalid&&!arready)physical_ar_stall=physical_ar_stall+1;
                if(awvalid&&!awready)aw_stall=aw_stall+1;
                if(wleft!=0&&!wready)w_stall=w_stall+1;
                if(dut.bank_core.engine.tone_valid&&!dut.bank_core.engine.tone_ready)tone_stall=tone_stall+1;
                if(dut.bank_core.engine.result_valid&&!dut.bank_core.engine.result_ready)core_output_stall=core_output_stall+1;
                if(dut.bank_core.engine.core.sampler.cache.out_valid&&!dut.bank_core.engine.core.sampler.cache.out_ready)cache_output_stall=cache_output_stall+1;
                if(dut.input_link.dma_awvalid&&dut.input_link.core_awvalid)write_contention=write_contention+1;
                if(dut.reader.arvalid&&dut.bank_core.arvalid)read_contention=read_contention+1;
                if(dut.input_link.input_dma.capture.unused_used>peak_input_fifo)peak_input_fifo=dut.input_link.input_dma.capture.unused_used;
                if(fifo_used>peak_output_fifo)peak_output_fifo=fifo_used;
            end
            if(dut.input_link.input_dma.grant_valid&&dut.input_link.input_dma.grant_ready)begin
                f=dut.input_link.input_dma.next_id-1;bank=dut.input_link.input_dma.grant_bank;
                if(f<0||f>=SIM_FRAMES||capture_reserved[bank]||source_epoch[bank]>=0&&releases[source_epoch[bank]]!=1)$fatal(1,"input bank reservation reused an unreleased source");
                source_epoch[bank]=f;source_bank_for[f]=bank;log_event("source_reserved",f,bank,$time);
            end
            if(processing)begin
                f=dut.bank_core.accepted_id-1;
                if(f<0||f>=SIM_FRAMES||source_epoch[dut.bank_core.active_source]!=f||!capture_reserved[dut.bank_core.active_source])$fatal(1,"processing unowned source epoch");
                if(dut.bank_core.engine.core.sampler.cache.inner.state==4)scatter_cycles[f]=scatter_cycles[f]+1;
                if(dut.bank_core.engine.result_valid&&dut.bank_core.engine.result_ready)begin
                    if(dut.bank_core.engine.result_tag>=N||dut.bank_core.engine.result_masked!==masks[texture(f)*N+dut.bank_core.engine.result_tag])$fatal(1,"CPU independent geometry mask mismatch");
                end
                if(dut.bank_core.engine.core.sampler.cache.inner.scatter_write&&dut.bank_core.engine.core.sampler.cache.inner.scatter_group==31)begin
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
                    if(f<0||f>=SIM_FRAMES||!processing||bank!=2+write_bank||(display_active&&write_bank==front_bank))$fatal(1,"result writes locked/wrong bank");
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
                if(wleft==0&&!first_w||tf<0||tf>=SIM_FRAMES||wstrb!==32'hffffffff||wlast!=(!first_w&&wleft==1))$fatal(1,"physical W owner/strobe/last mismatch");
                if(wdata!==oracle_word(tf,to,tb<2?0:1))$fatal(1,"actual DMA/result W differs from independent CPU pixels ID=%0d bank=%0d beat=%0d",tf+1,tb,to);
                if(tb<2)begin
                    source_written[tf]=source_written[tf]+1;total_source_beats=total_source_beats+1;
                    if(phase_id==0&&processing&&tf>dut.bank_core.accepted_id-1)future_capture_overlap[dut.bank_core.accepted_id-1]=future_capture_overlap[dut.bank_core.accepted_id-1]+1;
                end else begin result_written[tf]=result_written[tf]+1;total_result_beats=total_result_beats+1;end
                memory[ti]<=wdata;wleft<=first_w?15:wleft-1;windex<=ti+1;
            end
            if(rleft!=0&&wleft!=0&&rbank==wbank)$fatal(1,"physical R/W simultaneously own one bank");
            #1;stamp=$time-1;
            if(source_commit&&!previous_commit)begin
                f=source_commit_id-1;
                if(f<0||f>=SIM_FRAMES||commits[f]!=0||f!=commit_total||source_pixels!=N||source_crc!==source_crcs[texture(f)]||source_written[f]!=FB||input_pixels[f]!=N||source_epoch[source_commit_bank]!=f)$fatal(1,"input commit ID/actual DMA/source CRC/count mismatch");
                commits[f]=1;commit_total=commit_total+1;commit_ps[f]=stamp;begins[f]=cache_misses;observed_source_crc[f]=source_crc;
                cache_lines_seen=0;live_cache_lines=0;log_event("source_commit",f,source_commit_bank,stamp);
            end
            if(source_release&&!previous_release)begin
                f=source_release_id-1;
                if(f<0||f>=SIM_FRAMES||releases[f]!=0||commits[f]!=1||source_epoch[released_bank]!=f||result_written[f]!=FB||
                   (rleft!=0&&rbank==released_bank)||dut.bank_core.arvalid||dut.bank_core.awvalid||
                   (wleft!=0&&wbank==2+write_bank))$fatal(1,"source release before actual source/result drain");
                if(scatter_cycles[f]!=32*(cache_misses-begins[f]))$fatal(1,"scatter4 fill count mismatch");
                releases[f]=1;release_total=release_total+1;release_ps[f]=stamp;fills[f]=cache_misses-begins[f];process_cycles[f]=last_process_cycles;
                log_event("source_release",f,released_bank,stamp);
            end
            if(result_publish&&!previous_publish)begin
                f=publish_id-1;
                if(f<0||f>=SIM_FRAMES||publications[f]!=0||result_epoch[publish_bank-2]!=f)$fatal(1,"wrong/duplicate result publication");
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
                if(pf<0||pf>=SIM_FRAMES||result_epoch[pix_frame_bank]!=pf)$fatal(1,"actual scanner ID/bank epoch differs");
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
                    if(pf<0||pf>=SIM_FRAMES||scan_count!=N||pix_done_crc!==result_crcs[texture(pf)]||~scan_crc!==pix_done_crc)$fatal(1,"good done is not supported by actual DE/RGB scan");
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
    // Common source for small and native. No proxy core or modeled display FIFO.
    reg [48:0] corrected_maps[0:N-1],corrected_rotated[0:N-1];
    reg [24:0] corrected_raw[0:N-1];
    integer coord_checked[0:2],rot_checked[0:2],map_checked[0:2],sample_checked[0:2],raw_checked[0:2],tone_checked[0:2];
    integer writer_done_count[0:2],engine_done_count[0:2],reader_done_count[0:2],layer_csv;
    integer cache_epochs[0:2],cache_outer_epochs[0:2],cache_prevalid[0:2],source_ars[0:2],refills[0:2];
    integer first_query_wait_cycles=0;
    integer first_queries[0:2],poison_count=0,same_aw_first=0,delayed_aw_first=0,qf,qo,qi,ef,ei,valid_before;
    reg [27:0] epoch_base;reg [6:0] refill_line;reg [24:0] refill_block;
    reg epoch_check=0,refill_check=0;
    reg held_c=0,held_s=0,held_r=0;reg [71:0] saved_c;reg [72:0] saved_s;reg [48:0] saved_r;
    wire [367:0] config_snapshot={dut.bank_core.frame_out_cx,dut.bank_core.frame_out_cy,dut.bank_core.frame_src_cx,dut.bank_core.frame_src_cy,dut.bank_core.frame_src_fx,dut.bank_core.frame_src_fy,dut.bank_core.frame_inv_fx,dut.bank_core.frame_inv_fy,dut.bank_core.frame_k1,dut.bank_core.frame_k2,dut.bank_core.frame_k3,dut.bank_core.frame_p1,dut.bank_core.frame_p2};
    wire [367:0] expected_config={VEC_OUT_CX,VEC_OUT_CY,VEC_SRC_CX,VEC_SRC_CY,VEC_SRC_FX,VEC_SRC_FY,VEC_INV_FX,VEC_INV_FY,VEC_K1,VEC_K2,VEC_K3,VEC_P1,VEC_P2};
    wire [71:0] coord_bundle={dut.bank_core.engine.u,dut.bank_core.engine.v,dut.bank_core.engine.raster_tag[23:0]};
    wire [72:0] sample_bundle={dut.bank_core.engine.core.sample_mask,dut.bank_core.engine.core.sample_x,dut.bank_core.engine.core.sample_y,dut.bank_core.engine.core.sample_tag};
    wire [48:0] raw_bundle={dut.bank_core.engine.result_masked,dut.bank_core.engine.result_tag,dut.bank_core.engine.result_rgb};
    task automatic apply_payload(input integer frame);
        begin
            {live_out_cx,live_out_cy,live_src_cx,live_src_cy,live_src_fx,live_src_fy,live_inv_fx,live_inv_fy,live_k1,live_k2,live_k3,live_p1,live_p2}=expected_config;
            rot_cx=VEC_OUT_CX;rot_cy=VEC_OUT_CY;rot_cos=32'sd1073741824;rot_sin=0;
            gamma_enable=0;correction_enable=1'b1;
        end
    endtask
    integer cf;
    initial begin
        wait(rst_n);
        for(cf=0;cf<SIM_FRAMES;cf=cf+1)begin
            @(negedge core_clk);apply_payload(cf);
            do @(posedge core_clk);while(!(dut.src_valid&&dut.src_ready));
            #1;
            if(dut.bank_core.accepted_id!=cf+1||config_snapshot!==expected_config||dut.bank_core.frame_correction_enable!==(1'b1)||dut.bank_core.frame_gamma_enable||dut.bank_core.frame_rot_cos!==32'sd1073741824||dut.bank_core.frame_rot_sin!==32'sd0)$fatal(1,"actual source-commit482bit payload absent ID%0d",cf+1);
            @(negedge core_clk);
            {live_out_cx,live_out_cy,live_src_cx,live_src_cy,live_src_fx,live_src_fy}={6{24'hbad123}};
            {live_inv_fx,live_inv_fy,live_k1,live_k2,live_k3,live_p1,live_p2}={7{32'hbad12345}};
            rot_cx=-123456;rot_cy=654321;rot_cos=-7654321;rot_sin=1234567;gamma_enable=1;correction_enable=!(1'b1);poison_count=poison_count+1;
        end
    end
    always @(posedge core_clk)begin
        if(!rst_n)begin
            held_c<=0;held_s<=0;held_r<=0;
            for(qi=0;qi<SIM_FRAMES;qi=qi+1)begin coord_checked[qi]=0;rot_checked[qi]=0;map_checked[qi]=0;sample_checked[qi]=0;raw_checked[qi]=0;tone_checked[qi]=0;source_ars[qi]=0;writer_done_count[qi]=0;engine_done_count[qi]=0;reader_done_count[qi]=0;end
        end else begin
            if(held_c&&(!dut.bank_core.engine.coordinate_valid||coord_bundle!==saved_c))$fatal(1,"coordinate hold unstable");
            if(held_s&&(!dut.bank_core.engine.core.sample_valid||sample_bundle!==saved_s))$fatal(1,"selected sample hold unstable");
            if(held_r&&(!dut.bank_core.engine.result_valid||raw_bundle!==saved_r))$fatal(1,"RGB/mask/tag hold unstable");
            held_c<=dut.bank_core.engine.coordinate_valid&&!dut.bank_core.engine.coordinate_ready;saved_c<=coord_bundle;
            held_s<=dut.bank_core.engine.core.sample_valid&&!dut.bank_core.engine.core.sample_ready;saved_s<=sample_bundle;
            held_r<=dut.bank_core.engine.result_valid&&!dut.bank_core.engine.result_ready;saved_r<=raw_bundle;
            qf=dut.bank_core.accepted_id-1;
            if(processing||pending)begin
                if(qf<0||qf>=SIM_FRAMES||config_snapshot!==expected_config||dut.bank_core.frame_correction_enable!==(1'b1)||dut.bank_core.frame_gamma_enable||dut.bank_core.frame_rot_cx!==VEC_OUT_CX||dut.bank_core.frame_rot_cy!==VEC_OUT_CY||dut.bank_core.frame_rot_cos!==32'sd1073741824||dut.bank_core.frame_rot_sin!==32'sd0)$fatal(1,"accepted source snapshot drift/mixed mode ID%0d",qf+1);
            end
            if(dut.bank_core.engine.coordinate_valid&&dut.bank_core.engine.coordinate_ready)begin
                qo=dut.bank_core.engine.raster_tag;
                if(qf<0||qf>=SIM_FRAMES||coord_checked[qf]>=N||qo!=coord_checked[qf]||dut.bank_core.engine.u!==(qo%W)*256||dut.bank_core.engine.v!==(qo/W)*256||dut.bank_core.engine.tiled_mode||dut.bank_core.engine.core.frame_correction_enable!==(1'b1))$fatal(1,"coordinate/mode/raster scaling");
                coord_checked[qf]=coord_checked[qf]+1;
            end
            if(dut.bank_core.engine.core.rotation_valid&&dut.bank_core.engine.core.rotation_ready)begin
                qo=dut.bank_core.engine.core.rotated_tag;
                if(qf!=0||qo!=rot_checked[qf]||{dut.bank_core.engine.core.rotation_black,dut.bank_core.engine.core.rotated_u,dut.bank_core.engine.core.rotated_v}!==corrected_rotated[qo])$fatal(1,"corrected rotation oracle/epoch");
                rot_checked[qf]=rot_checked[qf]+1;
            end
            if(dut.bank_core.engine.core.mapped_valid&&dut.bank_core.engine.core.mapped_ready)begin
                qo=dut.bank_core.engine.core.mapped_tag;
                if(qf!=0||qo!=map_checked[qf]||{dut.bank_core.engine.core.mapped_black,dut.bank_core.engine.core.mapped_x,dut.bank_core.engine.core.mapped_y}!==corrected_maps[qo])$fatal(1,"corrected Brown oracle/epoch");
                map_checked[qf]=map_checked[qf]+1;
            end
            if(processing&&qf!=0&&(dut.bank_core.engine.core.rotation_valid||dut.bank_core.engine.core.mapped_valid))$fatal(1,"raw path leaked inactive geometry");
            if(dut.bank_core.engine.core.sample_valid&&dut.bank_core.engine.core.sample_ready)begin
                qo=dut.bank_core.engine.core.sample_tag;
                if(qf<0||qf>=SIM_FRAMES||qo!=sample_checked[qf])$fatal(1,"sample tags/epoch");
                if(1'b1)begin
                    if(dut.bank_core.engine.core.sample_mask!==corrected_raw[qo][24]||{dut.bank_core.engine.core.sample_x,dut.bank_core.engine.core.sample_y}!==corrected_maps[qo][47:0])$fatal(1,"corrected sampler coordinate/mask");
                end else if(dut.bank_core.engine.core.sample_mask||dut.bank_core.engine.core.sample_x!==(qo%W)*256||dut.bank_core.engine.core.sample_y!==(qo/W)*256)$fatal(1,"raw sampler coordinate/mask");
                sample_checked[qf]=sample_checked[qf]+1;
            end
            if(dut.bank_core.engine.result_valid&&dut.bank_core.engine.result_ready)begin
                qo=dut.bank_core.engine.result_tag;
                if(qf<0||qf>=SIM_FRAMES||qo!=raw_checked[qf])$fatal(1,"RGB tags/epoch");
                if(1'b1)begin if({dut.bank_core.engine.result_masked,dut.bank_core.engine.result_rgb}!==corrected_raw[qo])$fatal(1,"corrected RGB24/mask");end
                else if(dut.bank_core.engine.result_masked||dut.bank_core.engine.result_rgb!==expand565(sources[texture(qf)*N+qo]))$fatal(1,"raw RGB24/source equality");
                raw_checked[qf]=raw_checked[qf]+1;
            end
            if(dut.bank_core.engine.tone_valid&&dut.bank_core.engine.tone_ready)begin
                qo=dut.bank_core.engine.tone_tag;
                if(qf<0||qf>=SIM_FRAMES||qo!=tone_checked[qf]||dut.bank_core.gamma_mode!=0||dut.bank_core.engine.tone_pixel!==goldens[texture(qf)*N+qo]||dut.bank_core.engine.tone_masked!==((1'b1) ? corrected_raw[qo][24]:1'b0)||dut.bank_core.engine.tone.unused_sof!==(qo==0)||dut.bank_core.engine.tone.unused_eof!==(qo==N-1))$fatal(1,"disabled Gamma/pixel/mask/SOF/EOF");
                tone_checked[qf]=tone_checked[qf]+1;
            end
            if(arvalid&&arready&&arlen==7)source_ars[qf]=source_ars[qf]+1;
            if(dut.bank_core.engine.writer_done)writer_done_count[qf]=writer_done_count[qf]+1;
            if(dut.bank_core.engine_done)engine_done_count[qf]=engine_done_count[qf]+1;
            if(dut.reader_done)begin
                if(dut.lease_id<1||dut.lease_id>SIM_FRAMES)$fatal(1,"reader completion lease ID");
                reader_done_count[dut.lease_id-1]=reader_done_count[dut.lease_id-1]+1;
            end
            if(awvalid&&awready)begin if(wready)same_aw_first=same_aw_first+1;else delayed_aw_first=delayed_aw_first+1;end
        end
    end
    // Same-source ABA would hide stale image bytes. Verify the ACTUAL cache
    // epoch invalidation and refills, not a coincidentally equal CRC.
    always @(posedge core_clk)begin
        if(!rst_n)begin
            epoch_check=0;refill_check=0;
            for(ei=0;ei<SIM_FRAMES;ei=ei+1)begin cache_epochs[ei]=0;cache_outer_epochs[ei]=0;cache_prevalid[ei]=0;refills[ei]=0;first_queries[ei]=0;end
        end else begin
            ef=dut.bank_core.accepted_id-1;epoch_check=0;refill_check=0;
            if(dut.bank_core.engine.core.sampler.cache.accept_frame)cache_outer_epochs[ef]=cache_outer_epochs[ef]+1;
            if(dut.bank_core.engine.core.sampler.cache.inner.accept_frame)begin
                if(ef<0||ef>=SIM_FRAMES||dut.bank_core.engine.core.sampler.cache.queue_count||dut.bank_core.engine.core.sampler.cache.inner.query_valid||dut.bank_core.engine.core.sampler.cache.inner.v0||dut.bank_core.engine.core.sampler.cache.inner.v1||dut.bank_core.engine.core.sampler.cache.inner.state!=0)$fatal(1,"new epoch before query/oldframe drain");
                cache_epochs[ef]=cache_epochs[ef]+1;valid_before=|dut.bank_core.engine.core.sampler.cache.inner.valid_lines;
                cache_prevalid[ef]=valid_before;if(ef>0&&!valid_before)$fatal(1,"reused epoch did not start from populated cache");
                epoch_base=(ef%2)*STRIDE;epoch_check=1;
            end
            if(ef>=0&&ef<SIM_FRAMES&&!first_queries[ef]&&dut.bank_core.engine.core.sampler.cache.inner.query_valid&&dut.bank_core.engine.core.sampler.cache.inner.state==0&&(|dut.bank_core.engine.core.sampler.cache.inner.in_bounds))begin
                if(dut.bank_core.engine.core.sampler.cache.inner.accept_query)begin
                    if(dut.bank_core.engine.core.sampler.cache.inner.accept_fast||!dut.bank_core.engine.core.sampler.cache.inner.accept_slow)$fatal(1,"new epoch accepted first query reused stale cache");
                    first_queries[ef]=1;
                end else first_query_wait_cycles=first_query_wait_cycles+1;
            end
            if(dut.bank_core.engine.core.sampler.cache.inner.scatter_write&&dut.bank_core.engine.core.sampler.cache.inner.scatter_group==31)begin
                refill_line=dut.bank_core.engine.core.sampler.cache.inner.selected_line;refill_block=dut.bank_core.engine.core.sampler.cache.inner.selected_block;refill_check=1;refills[ef]=refills[ef]+1;
            end
            if(epoch_check||refill_check)begin
                #1;
                if(epoch_check&&(dut.bank_core.engine.core.sampler.cache.inner.valid_lines!==128'd0||dut.bank_core.engine.core.sampler.cache.inner.base!==epoch_base||dut.bank_core.engine.core.sampler.cache.inner.state!=0||dut.bank_core.engine.core.sampler.cache.inner.query_valid||dut.bank_core.engine.core.sampler.cache.inner.v0||dut.bank_core.engine.core.sampler.cache.inner.v1))$fatal(1,"postNBA cache invalidation/base/empty failed");
                if(epoch_check)log_event("cache_epoch_clear",ef,ef%2,$time-1);
                if(refill_check&&(!dut.bank_core.engine.core.sampler.cache.inner.valid_lines[refill_line]||dut.bank_core.engine.core.sampler.cache.inner.tags[refill_line]!==refill_block))$fatal(1,"refill valid/tag published incorrectly");
            end
        end
    end

    initial begin
        if(SIM_FRAMES!=1||!NATIVE||W%16||H%8||N%256||STRIDE<FU||VEC_RADIUS_GUARD_Q22!=1387217)$fatal(1,"single exact-Penn scale/layout");
        if(SIM_HT!=2200||SIM_VT!=1125||SIM_X0!=192||SIM_Y0!=41||SIM_HS!=44||SIM_VS!=5)$fatal(1,"native raster");
        $readmemh("source0.mem",sources,0,N-1);$readmemh("source1.mem",sources,N,2*N-1);
        $readmemh("expected0.mem",goldens,0,N-1);$readmemh("expected1.mem",goldens,N,2*N-1);
        $readmemh("masks0.mem",masks,0,N-1);$readmemh("masks1.mem",masks,N,2*N-1);
        $readmemh("sourcecrc0.mem",source_crcs,0,0);$readmemh("sourcecrc1.mem",source_crcs,1,1);
        $readmemh("crc0.mem",result_crcs,0,0);$readmemh("crc1.mem",result_crcs,1,1);
        $readmemh("corrected_maps.mem",corrected_maps);$readmemh("corrected_rotated.mem",corrected_rotated);$readmemh("corrected_raw.mem",corrected_raw);
        for(i=0;i<2*N;i=i+1)begin source_words[i/16][(i%16)*16+:16]=sources[i];result_words[i/16][(i%16)*16+:16]=goldens[i];end
        for(i=0;i<N;i=i+1)if(sources[i]!==sources[N+i]||goldens[i]!==sources[i])$fatal(1,"source was geometrically precorrected/swapped");
        if(source_crcs[0]!==32'hc14e962f||source_crcs[0]!==source_crcs[1]||result_crcs[0]!==source_crcs[0]||result_crcs[1]===source_crcs[0])$fatal(1,"source240 identity/difference");
        events=$fopen("events.csv","w");frames_csv=$fopen("frames.csv","w");scans_csv=$fopen("scans.csv","w");layer_csv=$fopen("layers.csv","w");
        $fdisplay(events,"event,phase,frame_id,physical_bank,time_ps");
        $fdisplay(frames_csv,"frame_id,source_bank,result_bank,input_pixels,source_beats,result_beats,commits,releases,publishes,unique_scans,input_first_ps,input_last_ps,commit_ps,source_release_ps,publish_ps,scan_start_ps,scan_last_pixel_ps,scan_done_ps,fills,scatter_cycles,hardware_process_cycles,future_capture_write_overlap_cycles,source_crc32,scan_crc32");
        $fdisplay(scans_csv,"phase,frame_id,physical_bank,scan_index,scanned_pixels,done_ps,crc32,unique_total");
        $fdisplay(layer_csv,"frame_id,correction,coordinate,rotation,map,sample,raw,tone,cache_epoch,outer_epoch,prevalid,first_query_miss,source_ar,refills,writer_done,engine_done,reader_done");
        $display("PENN_SYSTEM_BEGIN native1920x1080 source240 exact13 zeroangle gamma0 singleframe realDMA DDR-not-preloaded realFIFO pixelscan");
        clear_scoreboard();reset_domains(0);send_frames(1);
        wait(unique_total==1);@(negedge core_clk);scan_enable=0;wait_drain();
        if(captured_frames!=1||processed_frames!=1||presented_frames!=1||commit_total!=1||release_total!=1||publish_total!=1||unique_total!=1||scan_repeat_frames||total_source_beats!=FB||total_result_beats!=FB||total_readback_beats!=FB||queries!=N||underflows||mismatches||dut.input_link.dropped_frames||dut.input_link.overflow_frames||dut.input_link.no_free_frames||poison_count!=1||dut.bank_core.gamma_frames!=1)$fatal(1,"single realframe count/drain");
        i=0;
        if(input_pixels[i]!=N||source_written[i]!=FB||result_written[i]!=FB||commits[i]!=1||releases[i]!=1||publications[i]!=1||unique_scans[i]!=1||scan_pixels[i]!=N||source_bank_for[i]!=0||result_bank_for[i]!=2||coord_checked[i]!=N||sample_checked[i]!=N||raw_checked[i]!=N||tone_checked[i]!=N||rot_checked[i]!=N||map_checked[i]!=N||cache_epochs[i]!=1||cache_outer_epochs[i]!=1||cache_prevalid[i]!=0||!first_queries[i]||source_ars[i]==0||source_ars[i]!=refills[i]||refills[i]!=fills[i]||writer_done_count[i]!=1||engine_done_count[i]!=1||reader_done_count[i]!=1)$fatal(1,"realframe perlayer/owner");
        $fdisplay(frames_csv,"%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%08x,%08x",1,source_bank_for[i],result_bank_for[i],input_pixels[i],source_written[i],result_written[i],commits[i],releases[i],publications[i],unique_scans[i],first_ps[i],last_ps[i],commit_ps[i],release_ps[i],publish_ps[i],scan_start_ps[i],scan_last_ps[i],scan_done_ps[i],fills[i],scatter_cycles[i],process_cycles[i],future_capture_overlap[i],observed_source_crc[i],observed_scan_crc[i]);
        $fdisplay(layer_csv,"1,1,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d",coord_checked[i],rot_checked[i],map_checked[i],sample_checked[i],raw_checked[i],tone_checked[i],cache_epochs[i],cache_outer_epochs[i],cache_prevalid[i],first_queries[i],source_ars[i],refills[i],writer_done_count[i],engine_done_count[i],reader_done_count[i]);
        if(first_query_wait_cycles==0)$fatal(1,"masked-prefix first supported query never waited");
        if(physical_ar_stall==0||aw_stall==0||w_stall==0||cache_output_stall==0||core_output_stall==0||tone_stall==0||same_aw_first==0||delayed_aw_first==0)$fatal(1,"singleframe actual pressure");
        if(forced_result_aw_hold_cycles||forced_display_ar_hold_cycles||forced_write_dual_clients_seen||forced_read_dual_clients_seen||future_capture_overlap[0])$fatal(1,"singleframe scope changed");
        summary=$fopen("summary.json","w");
        $fdisplay(summary,"{\"passed\":true,\"frames_input\":1,\"frames_processed\":1,\"frames_unique_scanned\":1,\"pixels_each\":%0d,\"total_scanned_pixels\":%0d,\"total_cycles\":%0d,\"source_beats\":%0d,\"result_beats\":%0d,\"display_beats\":%0d,\"ar_stall\":%0d,\"aw_stall\":%0d,\"w_stall\":%0d,\"cache_output_stall\":%0d,\"core_output_stall\":%0d,\"tone_stall\":%0d,\"write_contention\":%0d,\"read_contention\":%0d,\"same_aw_first\":%0d,\"delayed_aw_first\":%0d,\"peak_input_fifo\":%0d,\"peak_output_fifo\":%0d,\"peak_cache_lines\":%0d,\"blank_rasters\":%0d,\"repeat_frames\":%0d,\"underflows\":%0d,\"crc_mismatches\":%0d,\"dropped_frames\":%0d,\"overflow_frames\":%0d,\"no_free_frames\":%0d,\"poison\":%0d,\"cache_epochs\":[%0d],\"cache_prevalid\":[%0d],\"cache_refills\":[%0d],\"first_query_wait_cycles\":%0d,\"final_drain\":true}",N,normal_scanned_pixels,ticks,total_source_beats,total_result_beats,total_readback_beats,physical_ar_stall,aw_stall,w_stall,cache_output_stall,core_output_stall,tone_stall,write_contention,read_contention,same_aw_first,delayed_aw_first,peak_input_fifo,peak_output_fifo,peak_cache_lines,blank_output_rasters,scan_repeat_frames,underflows,mismatches,dut.input_link.dropped_frames,dut.input_link.overflow_frames,dut.input_link.no_free_frames,poison_count,cache_epochs[0],cache_prevalid[0],refills[0],first_query_wait_cycles);
        $fclose(summary);$fclose(frames_csv);$fclose(scans_csv);$fclose(events);$fclose(layer_csv);
        $display("PASS PENN_SYSTEM: source240 exact13 fullpixel mask CRC realDMA actualFIFO scan drain pixels=%0d crc=%08x cycles=%0d",N,observed_scan_crc[0],ticks);$finish;
    end
endmodule
