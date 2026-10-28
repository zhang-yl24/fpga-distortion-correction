`timescale 1ps/1ps
// Three unthrottled timed source frames; normalized digital input, not hardware.
// Native cadence is exact74.25MHz/2200x1125. Small geometry is not30fps.
module tb_hdmi1080_continuous;
    `include "config.vh"
    `include "timing.vh"
    localparam W=VEC_WIDTH,H=VEC_HEIGHT,N=W*H,FB=N/16,FU=N/2;
    localparam STRIDE=1048576,MAX_CYCLES=SIM_MAX_CYCLES;
    localparam NATIVE=W==1920 && H==1080,SMALL=W==32 && H==16;
    localparam RATE_SAFE=SIM_DISPLAY_RATE>0 ? SIM_DISPLAY_RATE:1;
    localparam [63:0] FRAME_PERIOD_NUM_PS=64'd4000000*SIM_HT*SIM_VT;
    localparam [63:0] FRAME_PERIOD_FLOOR_PS=FRAME_PERIOD_NUM_PS/297;
    reg clk=0,pix_clk=0;always #4000 clk=~clk;
    // Half-period=2000000/297ps. Integer remainder carries across every
    // edge; accumulated timing error is less than1ps, not13ns rounding.
    integer pix_phase=0,pix_delay_ps;
    initial forever begin
        pix_phase=pix_phase+2000000;pix_delay_ps=pix_phase/297;
        pix_phase=pix_phase%297;#(pix_delay_ps)pix_clk=~pix_clk;
    end
    reg rst_n=0,input_enable=0,pix_vs=0,pix_de=0;reg [23:0] pix_rgb=0;
    wire source_valid,source_ready,source_bank;wire [31:0] source_id,source_crc,source_pixels;
    wire [1:0] source_writable,reserved;wire source_released,released_bank;
    reg display_request_valid=0,display_grant_ready=0,display_done_valid=0,display_done_bank=0;
    wire display_request_ready,display_grant_valid;wire [27:0] display_base;
    wire [31:0] display_crc,display_id;wire processing,pending,display_active,write_bank,front_bank;
    wire core_failed,link_failed;wire [7:0] core_fault,link_fault;
    wire [31:0] frames,last_cycles,hits,misses,queries;
    wire [27:0] sample_ar,core_aw;wire [3:0] sample_len,core_awlen;
    wire sample_valid,sample_ready,core_awvalid,core_awready,core_wready,core_wlast;
    wire [255:0] sample_data,core_wdata;wire sample_rvalid,sample_last;wire [3:0] sample_id;
    wire [31:0] core_wstrb;
    lens1080_bank_core #(.WIDTH(W),.HEIGHT(H),.BANK_STRIDE(STRIDE),.MAX_RADIUS_Q22(VEC_RADIUS_GUARD_Q22)) dut(
        .clk(clk),.rst_n(rst_n),.source_valid(source_valid),.source_ready(source_ready),
        .source_bank(source_bank),.source_id(source_id),.source_writable(source_writable),
        .source_released(source_released),.released_bank(released_bank),
        .display_request_valid(display_request_valid),.display_request_ready(display_request_ready),
        .display_grant_valid(display_grant_valid),.display_grant_ready(display_grant_ready),
        .display_base(display_base),.display_crc(display_crc),.display_id(display_id),
        .display_done_valid(display_done_valid),.display_done_bank(display_done_bank),
        .cfg_out_cx(VEC_OUT_CX),.cfg_out_cy(VEC_OUT_CY),.cfg_src_cx(VEC_SRC_CX),.cfg_src_cy(VEC_SRC_CY),
        .cfg_src_fx(VEC_SRC_FX),.cfg_src_fy(VEC_SRC_FY),.cfg_inv_fx(VEC_INV_FX),.cfg_inv_fy(VEC_INV_FY),
        .cfg_k1(VEC_K1),.cfg_k2(VEC_K2),.cfg_k3(VEC_K3),.cfg_p1(VEC_P1),.cfg_p2(VEC_P2),
        .araddr(sample_ar),.arlen(sample_len),.arvalid(sample_valid),.arready(sample_ready),
        .rdata(sample_data),.rvalid(sample_rvalid),.rlast(sample_last),.rid(sample_id),
        .awaddr(core_aw),.awlen(core_awlen),.awvalid(core_awvalid),.awready(core_awready),
        .wdata(core_wdata),.wstrb(core_wstrb),.wready(core_wready),.wlast(core_wlast),
        .processing(processing),.pending(pending),.display_active(display_active),
        .write_bank(write_bank),.front_bank(front_bank),.completed_frames(frames),.last_cycles(last_cycles),
        .hits(hits),.misses(misses),.queries(queries),.failed(core_failed),.fault(core_fault));
    wire [27:0] awaddr;wire [3:0] awlen;wire awvalid;reg awready=0,wready=0,wlast=0;
    wire [255:0] wdata;wire [31:0] wstrb;wire write_busy;
    wire [31:0] capture_bursts,result_bursts,accepted,dropped,overflowed,no_free;
    wire [7:0] last_drop;
    hdmi1080_input_write_link #(.WIDTH(W),.HEIGHT(H),.BANK_STRIDE(STRIDE),.FIFO_ADDR_BITS(6)) link(
        .pix_clk(pix_clk),.sys_clk(clk),.rst_n(rst_n),.enable(input_enable),
        .pix_vsync_active(pix_vs),.pix_de(pix_de),.pix_rgb(pix_rgb),
        .core_source_writable(source_writable),.core_source_released(source_released),.core_released_bank(released_bank),
        .core_source_valid(source_valid),.core_source_ready(source_ready),.core_source_bank(source_bank),
        .core_source_id(source_id),.source_crc(source_crc),.source_pixels(source_pixels),.capture_reserved(reserved),
        .core_failed(core_failed),.core_fault(core_fault),.core_awaddr(core_aw),.core_awlen(core_awlen),
        .core_awvalid(core_awvalid),.core_awready(core_awready),.core_wdata(core_wdata),.core_wstrb(core_wstrb),
        .core_wready(core_wready),.core_wlast(core_wlast),.awaddr(awaddr),.awlen(awlen),.awvalid(awvalid),.awready(awready),
        .wdata(wdata),.wstrb(wstrb),.wready(wready),.wlast(wlast),.failed(link_failed),.fault(link_fault),
        .write_busy(write_busy),.capture_bursts(capture_bursts),.result_bursts(result_bursts),
        .accepted_frames(accepted),.dropped_frames(dropped),.overflow_frames(overflowed),
        .no_free_frames(no_free),.last_drop_fault(last_drop));
    reg reader_start=0;wire reader_idle,reader_done,reader_failed;wire [7:0] reader_fault;
    wire [27:0] display_ar;wire [3:0] display_len;wire display_valid_ar,display_ready_ar;
    wire [255:0] display_data;wire display_rvalid,display_last;wire [3:0] display_rid;
    wire fifo_push;wire [255:0] fifo_data;wire [31:0] read_beats,read_crc,read_frames;
    integer ticks=0;
    wire [9:0] fake_fifo_used=ticks%127<8 ? 10'd500:10'd0;
    ddr_video_reader #(.FRAME_BEATS(FB)) reader(.clk(clk),.rst_n(rst_n),.start(reader_start),
        .base_address(display_base),.expected_checksum(display_crc),.fifo_used(fake_fifo_used),.fifo_ready(1'b1),
        .fifo_wr_en(fifo_push),.fifo_data(fifo_data),.araddr(display_ar),.arlen(display_len),
        .arvalid(display_valid_ar),.arready(display_ready_ar),.rdata(display_data),.rvalid(display_rvalid),
        .rlast(display_last),.rid(display_rid),.idle(reader_idle),.done(reader_done),.failed(reader_failed),
        .fault(reader_fault),.read_beats(read_beats),.last_checksum(read_crc),.completed_frames(read_frames));
    wire [27:0] araddr;wire [3:0] arlen;wire arvalid;reg arready=0;
    reg [255:0] rdata=0;reg rvalid=0,rlast=0;wire arb_failed,arb_busy;wire [7:0] arb_fault;
    wire [31:0] display_bursts,source_bursts;
    ddr_read_arbiter arb(.clk(clk),.rst_n(rst_n),.display_urgent(1'b0),
        .c0_araddr(display_ar),.c0_arlen(display_len),.c0_arvalid(display_valid_ar),.c0_arready(display_ready_ar),
        .c0_rdata(display_data),.c0_rvalid(display_rvalid),.c0_rlast(display_last),.c0_rid(display_rid),
        .c1_araddr(sample_ar),.c1_arlen(sample_len),.c1_arvalid(sample_valid),.c1_arready(sample_ready),
        .c1_rdata(sample_data),.c1_rvalid(sample_rvalid),.c1_rlast(sample_last),.c1_rid(sample_id),
        .araddr(araddr),.arlen(arlen),.arvalid(arvalid),.arready(arready),.rdata(rdata),.rvalid(rvalid),.rlast(rlast),.rid(4'd0),
        .failed(arb_failed),.fault(arb_fault),.busy(arb_busy),.bursts0(display_bursts),.bursts1(source_bursts));

    // Physical bank decode is separate from fixture epoch: bank0 is rewritten
    // with ID3 only after ID1 release. Source DDR is NEVER preloaded here.
    reg [255:0] memory[0:4*FB-1];
    reg [15:0] sources[0:3*N-1],goldens[0:3*N-1];
    // Read-only scoreboard lookup, packed ONCE from the independent fixtures.
    // These oracle arrays never initialize or write the modeled DDR memory.
    reg [255:0] oracle_source_words[0:3*FB-1],oracle_result_words[0:3*FB-1];
    reg masks[0:3*N-1];reg [31:0] source_crcs[0:2],result_crcs[0:2];
    integer source_epoch[0:1],result_epoch[0:1];
    integer source_banks[0:2],result_banks[0:2];
    integer input_pixels[0:2],source_written[0:2],result_written[0:2],readback_written[0:2];
    integer commits[0:2],releases[0:2],publications[0:2],grants[0:2],readbacks[0:2];
    integer begin_misses[0:2],begin_hits[0:2],fills[0:2],hit_counts[0:2];
    integer scatter_cycles[0:2],coordinate_stalls[0:2],tone_stalls[0:2],hardware_cycles[0:2];
    reg [63:0] sof_ps[0:3],first_ps[0:2],last_ps[0:2],commit_ps[0:2],release_ps[0:2];
    reg [63:0] publish_ps[0:2],grant_ps[0:2],readback_ps[0:2],slot_ps[0:2];
    integer rleft=0,rindex=0,rbank=0,rframe=-1,wleft=0,windex=0,wbank=0,wframe=-1,aw_count=0;
    integer source_checked=0,checked=0,read_checked=0,read_frame=-1,read_bank=-1;
    integer commit_total=0,release_total=0,publish_total=0,grant_total=0,readback_total=0;
    integer aw_stalls=0,w_stalls=0,physical_ar_stalls=0,commit_stalls=0;
    integer write_contention=0,read_contention=0,display_ar_stalls=0;
    integer same_aw_w[0:1],delayed_aw_w[0:1];
    integer tx_frame=-1,tx_x,tx_y,events,frames_csv,summary;
    reg source_window_closed=0,first_result_gate_done=0;
    integer forced_result_aw_wait=0;
    reg first_source_read_gate_done=0;
    integer forced_source_ar_wait=0;
    reg heldar=0,heldaw=0,heldw=0,heldcommit=0,heldgrant=0,heldtone=0;
    reg [27:0] saved_ar,saved_aw,saved_base;reg [3:0] saved_arlen,saved_awlen;
    reg [255:0] saved_w;reg [31:0] saved_id,saved_source_crc,saved_pixels,saved_display_crc,saved_display_id;
    reg saved_bank;reg [15:0] saved_tone;reg [23:0] saved_tag;
    reg previous_vs=0,previous_pending=0,previous_release=0,previous_grant=0,previous_reader_done=0;
    reg [63:0] stamp,period;
    integer f,off,bank,transfer_bank,transfer_index,transfer_frame,transfer_offset,client,i,init_frame,init_pixel;
    integer display_frame,display_slot=1;
    reg first_w;

    function automatic integer syscycle_at(input [63:0] when_ps);
        begin syscycle_at=when_ps>=4000 ? (when_ps-4000)/8000:0;end
    endfunction
    function automatic [255:0] packed_word(input integer epoch,input integer offset,input integer kind);
        begin
            packed_word=kind==0 ? oracle_source_words[epoch*FB+offset]:oracle_result_words[epoch*FB+offset];
        end
    endfunction
    function automatic [23:0] expand565(input [15:0] p);
        expand565={p[15:11],p[15:13],p[10:5],p[10:9],p[4:0],p[4:2]};
    endfunction
    task automatic log_event(input [8*24-1:0] kind,input integer epoch,input integer physical_bank,input [63:0] when_ps);
        begin
            $fdisplay(events,"%0s,%0d,%0d,%0d,%0d",kind,epoch+1,physical_bank,when_ps,syscycle_at(when_ps));
            $fflush(events);
        end
    endtask
    task automatic write_frame_row(input integer epoch);
        begin
            $fdisplay(frames_csv,"%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%08x,%08x",
                epoch,epoch+1,source_banks[epoch],result_banks[epoch],first_ps[epoch],last_ps[epoch],
                commit_ps[epoch],release_ps[epoch],publish_ps[epoch],grant_ps[epoch],readback_ps[epoch],
                (release_ps[epoch]-commit_ps[epoch])/8000,hardware_cycles[epoch],fills[epoch],scatter_cycles[epoch],
                coordinate_stalls[epoch],tone_stalls[epoch],syscycle_at(first_ps[epoch]),syscycle_at(last_ps[epoch]),
                syscycle_at(commit_ps[epoch]),syscycle_at(release_ps[epoch]),syscycle_at(publish_ps[epoch]),
                syscycle_at(grant_ps[epoch]),syscycle_at(readback_ps[epoch]),slot_ps[epoch],
                source_written[epoch],result_written[epoch],readback_written[epoch],source_crcs[epoch],result_crcs[epoch]);
            $fflush(frames_csv);
        end
    endtask

    // This source never consults grant/ready. Raster and fixture epoch advance
    // on every pixel tick even when the input DMA cannot reserve a bank.
    initial begin
        if(SIM_FRAMES!=3 || W%16!=0 || H%8!=0 || N%256!=0 || SIM_HT<SIM_X0+W ||
            SIM_VT<=SIM_Y0+H || SIM_Y0<SIM_VS || SIM_VS<1 || SIM_DISPLAY_RATE<0)
            $fatal(1,"invalid fixed-three-frame timing/geometry contract");
        if(NATIVE && (SIM_HT!=2200 || SIM_VT!=1125 || SIM_X0!=192 || SIM_Y0!=41 ||
            SIM_VS!=5 || SIM_DISPLAY_RATE!=60))$fatal(1,"native cadence must be exact2200x1125/74.25MHz with standard blanking");
        if(SMALL && (SIM_HT!=80 || SIM_VT!=40 || SIM_X0!=10 || SIM_Y0!=3 || SIM_VS!=1 || SIM_DISPLAY_RATE!=0))
            $fatal(1,"small pressure case must retain its declared80x40 cadence");
        $readmemh("source0.mem",sources,0,N-1);$readmemh("source1.mem",sources,N,2*N-1);$readmemh("source2.mem",sources,2*N,3*N-1);
        $readmemh("expected0.mem",goldens,0,N-1);$readmemh("expected1.mem",goldens,N,2*N-1);$readmemh("expected2.mem",goldens,2*N,3*N-1);
        $readmemh("masks0.mem",masks,0,N-1);$readmemh("masks1.mem",masks,N,2*N-1);$readmemh("masks2.mem",masks,2*N,3*N-1);
        $readmemh("sourcecrc0.mem",source_crcs,0,0);$readmemh("sourcecrc1.mem",source_crcs,1,1);$readmemh("sourcecrc2.mem",source_crcs,2,2);
        $readmemh("crc0.mem",result_crcs,0,0);$readmemh("crc1.mem",result_crcs,1,1);$readmemh("crc2.mem",result_crcs,2,2);
        for(init_pixel=0;init_pixel<3*N;init_pixel=init_pixel+1)begin
            oracle_source_words[init_pixel/16][(init_pixel%16)*16+:16]=sources[init_pixel];
            oracle_result_words[init_pixel/16][(init_pixel%16)*16+:16]=goldens[init_pixel];
        end
        if(source_crcs[2]===source_crcs[0] || result_crcs[2]===result_crcs[0])$fatal(1,"third frame must be a distinct epoch/golden");
        for(init_frame=0;init_frame<3;init_frame=init_frame+1)begin
            source_banks[init_frame]=-1;result_banks[init_frame]=-1;input_pixels[init_frame]=0;
            source_written[init_frame]=0;result_written[init_frame]=0;readback_written[init_frame]=0;
            commits[init_frame]=0;releases[init_frame]=0;publications[init_frame]=0;grants[init_frame]=0;readbacks[init_frame]=0;
            begin_misses[init_frame]=0;begin_hits[init_frame]=0;fills[init_frame]=0;hit_counts[init_frame]=0;
            scatter_cycles[init_frame]=0;coordinate_stalls[init_frame]=0;tone_stalls[init_frame]=0;hardware_cycles[init_frame]=0;
            sof_ps[init_frame]=0;first_ps[init_frame]=0;last_ps[init_frame]=0;commit_ps[init_frame]=0;
            release_ps[init_frame]=0;publish_ps[init_frame]=0;grant_ps[init_frame]=0;readback_ps[init_frame]=0;slot_ps[init_frame]=0;
        end
        sof_ps[3]=0;
        for(i=0;i<2;i=i+1)begin source_epoch[i]=-1;result_epoch[i]=-1;same_aw_w[i]=0;delayed_aw_w[i]=0;end
        events=$fopen("events.csv","w");frames_csv=$fopen("frames.csv","w");
        $fdisplay(events,"event,frame_id,physical_bank,time_ps,syscycle");$fflush(events);
        $fdisplay(frames_csv,"frame,frame_id,source_bank,result_bank,input_first_ps,input_last_ps,commit_ps,source_release_ps,result_publish_ps,display_grant_ps,readback_done_ps,processing_cycles,hardware_processing_counter,fills,scatter_cycles,coordinate_stall,tone_stall,input_first_syscycle,input_last_syscycle,commit_syscycle,release_syscycle,publish_syscycle,grant_syscycle,readback_syscycle,display_slot_ps,source_beats,result_beats,readback_beats,source_crc32,result_crc32");$fflush(frames_csv);
        repeat(12)@(negedge clk);rst_n=1;input_enable=1;
        @(negedge pix_clk);
        for(tx_frame=0;tx_frame<3;tx_frame=tx_frame+1)begin
            for(tx_y=0;tx_y<SIM_VT;tx_y=tx_y+1)begin
                for(tx_x=0;tx_x<SIM_HT;tx_x=tx_x+1)begin
                    pix_vs=tx_y<SIM_VS;
                    pix_de=tx_y>=SIM_Y0 && tx_y<SIM_Y0+H && tx_x>=SIM_X0 && tx_x<SIM_X0+W;
                    if(pix_de)pix_rgb=expand565(sources[tx_frame*N+(tx_y-SIM_Y0)*W+tx_x-SIM_X0]);
                    else pix_rgb=0;
                    @(negedge pix_clk);
                end
            end
        end
        // One terminal VS edge closes frame3. This is finite-window shutdown,
        // not a fourth active frame or a hardware loss-of-host watchdog.
        pix_de=0;pix_vs=1;pix_rgb=0;
        @(posedge pix_clk);@(negedge pix_clk);input_enable=0;source_window_closed=1;
    end

    always @(posedge pix_clk)begin
        if(!rst_n)previous_vs=0;
        else begin
            if(pix_vs && !previous_vs)begin
                if(tx_frame<0 || tx_frame>3)$fatal(1,"unexpected source SOF epoch");
                sof_ps[tx_frame]=$time;
                if(tx_frame==3)log_event("input_terminal_eof",2,-1,$time);
                else log_event("input_sof",tx_frame,-1,$time);
                if(tx_frame>0)begin
                    period=sof_ps[tx_frame]-sof_ps[tx_frame-1];
                    if(period!=FRAME_PERIOD_FLOOR_PS && period!=FRAME_PERIOD_FLOOR_PS+1)
                        $fatal(1,"source cadence changed/waited: frame=%0d period_ps=%0d",tx_frame,period);
                end
            end
            previous_vs=pix_vs;
            if(pix_de)begin
                if(tx_frame<0 || tx_frame>=3 || input_pixels[tx_frame]>=N)$fatal(1,"source duplicate/extra active pixel");
                if(input_pixels[tx_frame]==0)begin first_ps[tx_frame]=$time;log_event("input_first",tx_frame,-1,$time);end
                input_pixels[tx_frame]=input_pixels[tx_frame]+1;last_ps[tx_frame]=$time;
                if(input_pixels[tx_frame]==N)log_event("input_last",tx_frame,-1,$time);
            end
        end
    end

    // Native memory pressure is unchanged; only SMALL has the explicit
    // already-selected-result AW hold used in the prior bounded small case.
    always @(negedge clk)begin
        ticks=ticks+1;
        if(rst_n && ticks%1000000==0)
            $display("CONTINUOUS_PROGRESS time_ps=%0d syscycles=%0d input_pixels=%0d commits=%0d releases=%0d readbacks=%0d AW_bursts=%0d W_beats=%0d dropped=%0d no_free=%0d",$time,ticks,
                input_pixels[0]+input_pixels[1]+input_pixels[2],commit_total,release_total,readback_total,aw_count,source_checked+checked,dropped,no_free);
        if(ticks>MAX_CYCLES)begin
            log_event("cycle_timeout",tx_frame,-1,$time);
            $display("CONTINUOUS_TIMEOUT captured/committed=%0d processed=%0d readback=%0d dropped=%0d no_free=%0d",accepted,frames,readback_total,dropped,no_free);
            $fatal(1,"bounded continuous simulation cycle timeout");
        end
        arready=rst_n && rleft==0 && ticks%7>=2;
        // SMALL only: keep ID2's already selected source AR/owner unchanged
        // until display0 ALSO presents ARVALID. Waiting for acceptance before
        // starting the reader would not exercise both client requests pending.
        if(!rst_n)first_source_read_gate_done=0;
        else if(SMALL && processing && dut.accepted_id==2 &&
            !first_source_read_gate_done && arvalid && arb.owner)begin
            if(display_valid_ar)first_source_read_gate_done=1;
            else begin arready=0;forced_source_ar_wait=forced_source_ar_wait+1;end
        end
        rvalid=rst_n && rleft!=0 && ticks%5!=0;rlast=rleft==1;
        if(rvalid)rdata=memory[rindex];
        awready=rst_n && wleft==0 && ticks%9>=3;
        if(!rst_n)first_result_gate_done=0;
        else if(SMALL && !first_result_gate_done && awvalid && awaddr/STRIDE>=2)begin
            if(link.dma_awvalid)first_result_gate_done=1;
            else begin awready=0;forced_result_aw_wait=forced_result_aw_wait+1;end
        end
        wready=rst_n && (wleft!=0 || (awvalid && awready && aw_count%2==0)) && ticks%6!=0;
        wlast=wleft==1;
    end

    always @(posedge clk)begin
        if(!rst_n)begin
            rleft<=0;wleft<=0;heldar<=0;heldaw<=0;heldw<=0;heldcommit<=0;heldgrant<=0;heldtone<=0;
            previous_pending=0;previous_release=0;previous_grant=0;previous_reader_done=0;
        end else begin
            if(dropped!=0 || overflowed!=0 || no_free!=0)begin
                log_event("unexpected_drop",tx_frame,-1,$time);
                $display("CONTINUOUS_DROP time_ps=%0d source_frame=%0d accepted=%0d processed=%0d readback=%0d dropped=%0d overflow=%0d no_free=%0d last_fault=%h",$time,tx_frame+1,accepted,frames,readback_total,dropped,overflowed,no_free,last_drop);
                $fatal(1,"continuous normal source frame dropped; preserve partial events/frames");
            end
            if(core_failed || link_failed || reader_failed || arb_failed)begin
                log_event("chain_fault",tx_frame,-1,$time);
                $fatal(1,"continuous fault core=%h link=%h reader=%h arb=%h",core_fault,link_fault,reader_fault,arb_fault);
            end
            if(heldar && (!arvalid || araddr!==saved_ar || arlen!==saved_arlen))$fatal(1,"AR changed under backpressure");
            if(heldaw && (!awvalid || awaddr!==saved_aw || awlen!==saved_awlen))$fatal(1,"AW changed under backpressure");
            if(heldw && wdata!==saved_w)$fatal(1,"W payload changed under backpressure");
            if(heldcommit && (!source_valid || {source_bank,source_id,source_crc,source_pixels}!==
                {saved_bank,saved_id,saved_source_crc,saved_pixels}))$fatal(1,"source commit changed while stalled");
            if(heldgrant && (!display_grant_valid || {display_base,display_crc,display_id}!==
                {saved_base,saved_display_crc,saved_display_id}))$fatal(1,"display grant changed while stalled");
            if(heldtone && (!dut.engine.tone_valid || dut.engine.tone_pixel!==saved_tone || dut.engine.tone_tag!==saved_tag))
                $fatal(1,"tone/tag changed under output stall");
            heldar<=arvalid&&!arready;saved_ar<=araddr;saved_arlen<=arlen;
            heldaw<=awvalid&&!awready;saved_aw<=awaddr;saved_awlen<=awlen;
            heldw<=wleft!=0&&!wready;saved_w<=wdata;
            heldcommit<=source_valid&&!source_ready;saved_bank<=source_bank;saved_id<=source_id;
            saved_source_crc<=source_crc;saved_pixels<=source_pixels;
            heldgrant<=display_grant_valid&&!display_grant_ready;saved_base<=display_base;
            saved_display_crc<=display_crc;saved_display_id<=display_id;
            heldtone<=dut.engine.tone_valid&&!dut.engine.tone_ready;saved_tone<=dut.engine.tone_pixel;saved_tag<=dut.engine.tone_tag;
            if(arvalid&&!arready)physical_ar_stalls=physical_ar_stalls+1;
            if(awvalid&&!awready)aw_stalls=aw_stalls+1;
            if(wleft!=0&&!wready)w_stalls=w_stalls+1;
            if(source_valid&&!source_ready)commit_stalls=commit_stalls+1;
            if(link.dma_awvalid && core_awvalid)write_contention=write_contention+1;
            if(display_valid_ar && sample_valid)read_contention=read_contention+1;
            if(display_valid_ar&&!display_ready_ar)display_ar_stalls=display_ar_stalls+1;
            if(link.input_dma.grant_valid && link.input_dma.grant_ready)begin
                f=link.input_dma.next_id-1;bank=link.input_dma.grant_bank;
                if(f<0 || f>=3 || reserved[bank] || !source_writable[bank])$fatal(1,"unexpected/duplicate capture reservation");
                if(source_epoch[bank]>=0 && releases[source_epoch[bank]]!=1)$fatal(1,"source bank reused before old core release");
                source_epoch[bank]=f;source_banks[f]=bank;log_event("source_reserved",f,bank,$time);
            end
            if(source_valid)begin
                f=source_id-1;
                if(f<0 || f>=3 || source_epoch[source_bank]!=f || source_banks[f]!=source_bank ||
                    source_writable[source_bank] || !reserved[source_bank] || source_pixels!=N ||
                    source_written[f]!=FB || source_crc!==source_crcs[f] || input_pixels[f]!=N)
                    $fatal(1,"source commit geometry/ID/epoch/CRC/reservation mismatch");
                if(wleft!=0 && wbank==source_bank)$fatal(1,"source committed before own W drain");
            end
            if(source_valid&&source_ready)begin
                f=source_id-1;
                if(commits[f]!=0 || f!=commit_total)$fatal(1,"duplicate/out-of-order source commit");
                commits[f]=1;commit_total=commit_total+1;commit_ps[f]=$time;
                begin_misses[f]=misses;begin_hits[f]=hits;
                for(i=0;i<FB;i=i+1)if(memory[source_bank*FB+i]!==packed_word(f,i,0))$fatal(1,"source commit memory mismatch");
                log_event("source_commit",f,source_bank,$time);
            end
            if(processing)begin
                f=dut.accepted_id-1;
                if(f<0 || f>=3 || source_epoch[dut.active_source]!=f || source_writable[dut.active_source] || !reserved[dut.active_source])
                    $fatal(1,"processing wrong/unreserved source epoch");
                if(dut.engine.coordinate_valid&&!dut.engine.coordinate_ready)coordinate_stalls[f]=coordinate_stalls[f]+1;
                if(dut.engine.tone_valid&&!dut.engine.tone_ready)tone_stalls[f]=tone_stalls[f]+1;
                if(dut.engine.core.sampler.cache.inner.state==4)scatter_cycles[f]=scatter_cycles[f]+1;
                if(dut.engine.result_valid&&dut.engine.result_ready)begin
                    if(dut.engine.result_tag>=N)$fatal(1,"output tag outside frame");
                    else if(dut.engine.result_masked!==masks[f*N+dut.engine.result_tag])$fatal(1,"software geometry mask mismatch");
                end
            end
            if(arvalid&&arready)begin
                bank=araddr/STRIDE;off=araddr%STRIDE;
                if(rleft!=0 || bank>3 || off%8 || off+(arlen+1)*8>FU)$fatal(1,"physical AR outside frame");
                if(arlen==7)begin
                    f=source_epoch[bank];
                    if(bank>1 || f<0 || !processing || bank!=dut.active_source || dut.accepted_id!=f+1 ||
                        source_written[f]!=FB || off%64)$fatal(1,"source AR wrong ownership/epoch/alignment");
                end else if(arlen==15)begin
                    f=read_frame;
                    if(bank<2 || f<0 || !display_active || bank!=read_bank || bank!=2+front_bank ||
                        result_epoch[bank-2]!=f || display_id!=f+1 || result_written[f]!=FB || off%128)
                        $fatal(1,"display AR wrong ownership/epoch/alignment");
                end else $fatal(1,"unexpected read burst length");
                rleft<=arlen+1;rindex<=bank*FB+(off>>3);rbank<=bank;rframe<=f;
            end
            if(rvalid)begin
                if(rframe<0 || rdata!==packed_word(rframe,rindex-rbank*FB,rbank<2 ? 0:1))
                    $fatal(1,"physical R data stale/corrupt epoch");
                rleft<=rleft-1;rindex<=rindex+1;
            end
            if(awvalid&&awready)begin
                bank=awaddr/STRIDE;off=awaddr%STRIDE;
                if(wleft!=0 || awlen!=15 || bank>3 || off%128 || off+128>FU)$fatal(1,"physical AW outside frame/burst");
                client=bank<2 ? 0:1;
                if(bank<2)begin
                    f=source_epoch[bank];
                    if(f<0 || !reserved[bank] || (processing&&dut.active_source==bank) ||
                        (source_valid&&source_bank==bank))$fatal(1,"input AW writes locked/unreserved source bank");
                end else begin
                    f=dut.accepted_id-1;
                    if(!processing || f<0 || f>=3 || bank!=2+write_bank || (display_active&&write_bank==front_bank))
                        $fatal(1,"result AW writes locked/wrong bank");
                    if(result_epoch[bank-2]!=f)begin
                        if(off!=0 || result_written[f]!=0 || (result_epoch[bank-2]>=0 && readbacks[result_epoch[bank-2]]!=1))
                            $fatal(1,"result bank epoch reused before previous readback/unlock");
                        result_epoch[bank-2]=f;result_banks[f]=bank;
                    end
                end
                wleft<=16;windex<=bank*FB+(off>>3);wbank<=bank;wframe<=f;aw_count=aw_count+1;
                if(wready)same_aw_w[client]=same_aw_w[client]+1;else delayed_aw_w[client]=delayed_aw_w[client]+1;
            end
            if(wready)begin
                first_w=wleft==0 && awvalid && awready;
                transfer_bank=first_w ? bank:wbank;transfer_frame=first_w ? f:wframe;
                transfer_index=first_w ? bank*FB+(off>>3):windex;transfer_offset=transfer_index-transfer_bank*FB;
                if((wleft==0&&!first_w) || transfer_frame<0 || transfer_frame>=3 || wstrb!==32'hffffffff ||
                    wlast!=(!first_w&&wleft==1))$fatal(1,"physical W owner/strobe/last mismatch");
                if(transfer_bank<2)begin
                    if(source_epoch[transfer_bank]!=transfer_frame || !reserved[transfer_bank] ||
                        (processing&&dut.active_source==transfer_bank) || wdata!==packed_word(transfer_frame,transfer_offset,0))
                        $fatal(1,"source W software golden/epoch mismatch");
                    source_written[transfer_frame]=source_written[transfer_frame]+1;source_checked=source_checked+1;
                end else begin
                    if(!processing || result_epoch[transfer_bank-2]!=transfer_frame ||
                        wdata!==packed_word(transfer_frame,transfer_offset,1))$fatal(1,"corrected W software golden/epoch mismatch");
                    result_written[transfer_frame]=result_written[transfer_frame]+1;checked=checked+1;
                end
                memory[transfer_index]<=wdata;wleft<=first_w ? 15:wleft-1;windex<=transfer_index+1;
            end
            if(rleft!=0&&wleft!=0&&rbank==wbank)$fatal(1,"physical concurrent read/write same bank");
            if(fifo_push)begin
                if(read_frame<0 || fifo_data!==packed_word(read_frame,readback_written[read_frame],1))
                    $fatal(1,"display DDR readback golden/epoch mismatch");
                readback_written[read_frame]=readback_written[read_frame]+1;read_checked=read_checked+1;
            end

            // Sample registered events after NBA; subtract1ps to preserve their
            // actual source clock-edge timestamp, not the monitor's delta.
            #1;stamp=$time-1;
            if(source_released&&!previous_release)begin
                f=source_epoch[released_bank];
                if(f<0 || f>=3 || releases[f]!=0 || commits[f]!=1 || dut.accepted_id!=f+1 ||
                    (rleft!=0&&rbank==released_bank) || (arb_busy&&arb.owner) || sample_valid ||
                    (wleft!=0&&wbank==2+write_bank) || core_awvalid || queries!=(f+1)*N || result_written[f]!=FB)
                    $fatal(1,"source release before epoch/core read/result drain");
                if(dut.pending_crc!==result_crcs[f] || scatter_cycles[f]!=32*(misses-begin_misses[f]))
                    $fatal(1,"result CRC/scatter32 mismatch");
                for(i=0;i<FB;i=i+1)if(memory[released_bank*FB+i]!==packed_word(f,i,0))$fatal(1,"source overwritten before release");
                releases[f]=1;release_total=release_total+1;release_ps[f]=stamp;
                fills[f]=misses-begin_misses[f];hit_counts[f]=hits-begin_hits[f];hardware_cycles[f]=last_cycles;
                log_event("source_release",f,released_bank,stamp);
            end
            if(pending&&!previous_pending)begin
                f=dut.pending_id-1;
                if(f<0 || f>=3 || publications[f]!=0 || result_epoch[write_bank]!=f)$fatal(1,"duplicate/wrong result publication");
                publications[f]=1;publish_total=publish_total+1;publish_ps[f]=stamp;
                log_event("result_publish",f,2+write_bank,stamp);
            end
            if(display_grant_valid&&!previous_grant)begin
                f=display_id-1;bank=display_base/STRIDE;
                if(f<0 || f>=3 || grants[f]!=0 || f!=grant_total || publications[f]!=1 ||
                    bank!=result_banks[f] || display_crc!==result_crcs[f])$fatal(1,"stale/duplicate/out-of-order display grant");
                grants[f]=1;grant_total=grant_total+1;grant_ps[f]=stamp;
                log_event("display_grant",f,bank,stamp);
            end
            if(reader_done&&!previous_reader_done)begin
                f=read_frame;
                if(f<0 || f>=3 || readbacks[f]!=0 || f!=readback_total || read_beats!=FB ||
                    readback_written[f]!=FB || read_crc!==result_crcs[f] || !reader_idle)
                    $fatal(1,"readback count/CRC/epoch mismatch");
                readbacks[f]=1;readback_total=readback_total+1;readback_ps[f]=stamp;
                log_event("readback_done",f,read_bank,stamp);write_frame_row(f);
            end
            previous_release=source_released;previous_pending=pending;previous_grant=display_grant_valid;previous_reader_done=reader_done;
        end
    end

    initial begin
        wait(rst_n);
        for(display_frame=0;display_frame<3;display_frame=display_frame+1)begin
            // Only NEW pending IDs are requested. front_valid alone is never
            // used to repeat the preceding image and inflate frame counts.
            wait(pending && dut.pending_id==display_frame+1);
            if(NATIVE)begin
                slot_ps[display_frame]=sof_ps[0]+(64'd1000000000000*display_slot)/RATE_SAFE;
                while(slot_ps[display_frame]<=$time)begin
                    display_slot=display_slot+1;
                    slot_ps[display_frame]=sof_ps[0]+(64'd1000000000000*display_slot)/RATE_SAFE;
                end
                while($time<slot_ps[display_frame])@(negedge clk);
                log_event("display_slot",display_frame,-1,slot_ps[display_frame]);display_slot=display_slot+1;
            end else if(SMALL && display_frame==0)begin
                wait(source_valid && source_id==2);repeat(20)@(negedge clk);
            end
            @(negedge clk);display_request_valid=1;
            do @(posedge clk);while(!display_request_ready);
            @(negedge clk);display_request_valid=0;
            wait(display_grant_valid);repeat(9)@(negedge clk);
            if(display_id!=display_frame+1 || display_base%STRIDE!=0)$fatal(1,"wrong NEW result grant");
            read_frame=display_id-1;read_bank=display_base/STRIDE;
            display_grant_ready=1;@(negedge clk);display_grant_ready=0;
            if(SMALL && display_frame==0)begin
                do @(posedge clk);while(!sample_valid);@(negedge clk);
            end
            reader_start=1;@(negedge clk);reader_start=0;
            wait(reader_done);@(negedge clk);repeat(20)@(negedge clk);
            if(!reader_idle || (arb_busy&&!arb.owner) || (rleft!=0&&rbank==read_bank))$fatal(1,"readback not drained before front unlock");
            display_done_bank=read_bank-2;display_done_valid=1;log_event("display_unlock",read_frame,read_bank,$time+4000);
            @(negedge clk);display_done_valid=0;
        end
        wait(source_window_closed);repeat(30)@(negedge clk);
        if(frames!=3 || accepted!=3 || commit_total!=3 || release_total!=3 || publish_total!=3 || grant_total!=3 || readback_total!=3 ||
            queries!=3*N || source_checked!=3*FB || checked!=3*FB || read_checked!=3*FB || processing || pending ||
            display_active || display_grant_valid || source_valid || reserved!=0 || source_writable!==2'b11 ||
            link.input_dma.active || !link.input_dma.capture.fifo_idle || link.input_dma.crc_busy || write_busy ||
            arvalid || sample_valid || display_valid_ar || core_awvalid || awvalid || rleft!=0 || wleft!=0 || arb_busy ||
            !reader_idle || dropped!=0 || overflowed!=0 || no_free!=0 || last_drop!=0)
            $fatal(1,"continuous final counts/FIFO/ownership/DDR drain failed");
        for(i=0;i<3;i=i+1)begin
            if(input_pixels[i]!=N || source_written[i]!=FB || result_written[i]!=FB || readback_written[i]!=FB ||
                commits[i]!=1 || releases[i]!=1 || publications[i]!=1 || grants[i]!=1 || readbacks[i]!=1 ||
                source_banks[i]!=(i%2) || result_banks[i]!=2+(i%2) || last_ps[i]<first_ps[i] ||
                commit_ps[i]<last_ps[i] || release_ps[i]<commit_ps[i] || grant_ps[i]<publish_ps[i] || readback_ps[i]<grant_ps[i])
                $fatal(1,"continuous per-ID timestamps/counts/reuse failed frame=%0d",i+1);
        end
        if(write_contention==0 || read_contention==0 || aw_stalls==0 || w_stalls==0 || physical_ar_stalls==0 ||
            same_aw_w[0]+same_aw_w[1]==0 || delayed_aw_w[0]+delayed_aw_w[1]==0 ||
            (SMALL && (commit_stalls<20 || !first_result_gate_done ||
                !first_source_read_gate_done || forced_source_ar_wait==0)))begin
            log_event("coverage_failure",-1,-1,$time);
            $display("CONTINUOUS_COVERAGE_FAIL read_contention=%0d write_contention=%0d AR=%0d AW=%0d W=%0d commit=%0d same=%0d delayed=%0d",read_contention,write_contention,physical_ar_stalls,aw_stalls,w_stalls,commit_stalls,same_aw_w[0]+same_aw_w[1],delayed_aw_w[0]+delayed_aw_w[1]);
            $fatal(1,"declared pressure coverage missing; do not retune native phase");
        end
        summary=$fopen("summary.json","w");
        $fdisplay(summary,"{\"passed\":true,\"width\":%0d,\"height\":%0d,\"frames_input\":3,\"frames_committed\":%0d,\"frames_processed\":%0d,\"frames_readback\":%0d,\"source_beats\":%0d,\"result_beats\":%0d,\"readback_beats\":%0d,\"dropped_frames\":%0d,\"overflow_frames\":%0d,\"no_free_frames\":%0d,\"source_crc32\":[\"%08x\",\"%08x\",\"%08x\"],\"result_crc32\":[\"%08x\",\"%08x\",\"%08x\"],\"write_contention\":%0d,\"read_contention\":%0d,\"aw_stall\":%0d,\"w_stall\":%0d,\"physical_ar_stall\":%0d,\"commit_stall\":%0d,\"display_ar_stall\":%0d,\"same_aw_w\":[%0d,%0d],\"delayed_aw_w\":[%0d,%0d],\"capture_bursts\":%0d,\"result_bursts\":%0d,\"source_read_bursts\":%0d,\"display_read_bursts\":%0d,\"source_bank_sequence\":[%0d,%0d,%0d],\"result_bank_sequence\":[%0d,%0d,%0d],\"pix_clock_hz\":74250000,\"display_request_rate_hz\":%0d,\"input_continuous\":true,\"input_preloaded_not_DMA\":false,\"display_DDR_readback_only\":true,\"timestamp_unit\":\"ps\",\"final_drain\":true,\"hardware_verified\":false,\"forced_small_source_ar_wait\":%0d}",
            W,H,commit_total,frames,readback_total,source_checked,checked,read_checked,dropped,overflowed,no_free,
            source_crcs[0],source_crcs[1],source_crcs[2],result_crcs[0],result_crcs[1],result_crcs[2],
            write_contention,read_contention,aw_stalls,w_stalls,physical_ar_stalls,commit_stalls,display_ar_stalls,
            same_aw_w[0],same_aw_w[1],delayed_aw_w[0],delayed_aw_w[1],capture_bursts,result_bursts,source_bursts,display_bursts,
            source_banks[0],source_banks[1],source_banks[2],result_banks[0],result_banks[1],result_banks[2],SIM_DISPLAY_RATE,forced_source_ar_wait);
        $fclose(summary);$fclose(events);$fclose(frames_csv);
        $display("CONTINUOUS_PRESSURE read_contention=%0d write_contention=%0d AR=%0d AW=%0d W=%0d commit=%0d forced_small_AW_wait=%0d forced_small_AR_wait=%0d",read_contention,write_contention,physical_ar_stalls,aw_stalls,w_stalls,commit_stalls,forced_result_aw_wait,forced_source_ar_wait);
        $display("PASS hdmi1080 continuous: %0dx%0d three unthrottled timed input frames, independent software pixels/masks/CRCs, ID-bound bank reuse, shared DDR and complete readback/drain; not physical HDMI/STA/optics",W,H);
        $finish;
    end
endmodule

