`timescale 1ns/1ps
// Small actual-input integration, NOT a native1080 throughput benchmark.
module tb_hdmi1080_lens_core_small;
    `include "config.vh"
    localparam W=VEC_WIDTH,H=VEC_HEIGHT,N=W*H,FB=N/16,FU=N/2;
    localparam STRIDE=1048576,MAX_CYCLES=2000000;
    reg clk=0,pix_clk=0;always #4 clk=~clk;always #7 pix_clk=~pix_clk;
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
    hdmi1080_input_write_link #(.WIDTH(W),.HEIGHT(H),.BANK_STRIDE(STRIDE),.FIFO_ADDR_BITS(4)) link(
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

    // Only active frame ranges are modeled, indexed AFTER physical bank decode.
    // These words are deliberately NOT initialized from source.mem.
    reg [255:0] memory[0:4*FB-1];
    reg [15:0] src0[0:N-1],src1[0:N-1],gold0[0:N-1],gold1[0:N-1];
    reg mask0[0:N-1],mask1[0:N-1];reg [31:0] crc0[0:0],crc1[0:0],source_crc0[0:0],source_crc1[0:0];
    integer rleft=0,rindex=0,rbank=0,wleft=0,windex=0,wbank=0,aw_count=0;
    integer checked=0,source_checked=0,read_checked=0,read_frame=0;
    integer source_written[0:1],result_written[0:1],starts[0:1],begin_misses[0:1];
    integer scatter_cycles[0:1],coordinate_stall[0:1],tone_stall[0:1];
    integer aw_stalls=0,w_stalls=0,commit_stalls=0,write_contention=0,display_ar_stalls=0;
    reg first_result_gate_done=0;
    integer forced_result_aw_wait=0;
    integer same_aw_w[0:1],delayed_aw_w[0:1],csv,summary,first_start=0;
    reg heldar=0,heldaw=0,heldw=0,heldcommit=0,heldgrant=0;
    reg [27:0] saved_ar,saved_aw,saved_base;reg [3:0] saved_arlen,saved_awlen;
    reg [255:0] saved_w;reg [31:0] saved_id,saved_source_crc,saved_pixels,saved_display_crc,saved_display_id;
    reg saved_bank;
    function automatic [255:0] packed_word(input integer frame,input integer offset,input integer kind);
        integer j;
        begin for(j=0;j<16;j=j+1)begin
            if(kind==0)packed_word[j*16+:16]=frame==0 ? src0[offset*16+j]:src1[offset*16+j];
            else packed_word[j*16+:16]=frame==0 ? gold0[offset*16+j]:gold1[offset*16+j];
        end end
    endfunction
    function automatic [23:0] expand565(input [15:0] p);
        expand565={p[15:11],p[15:13],p[10:5],p[10:9],p[4:0],p[4:2]};
    endfunction
    always @(negedge clk)begin
        ticks=ticks+1;if(ticks>MAX_CYCLES)$fatal(1,"core-small2M cycle timeout");
        arready=rst_n && rleft==0 && ticks%7>=2;
        rvalid=rst_n && rleft!=0 && ticks%5!=0;rlast=rleft==1;
        if(rvalid)rdata=memory[rindex];
        awready=rst_n && wleft==0 && ticks%9>=3;
        // Hold the already selected first result AW, without changing owner,
        // until the real second input DMA also offers a burst. This is a new
        // small pressure case, not a cycle-performance comparison with case a.
        if(!rst_n)first_result_gate_done=0;
        else if(!first_result_gate_done && awvalid && awaddr/STRIDE>=2)begin
            if(link.dma_awvalid)first_result_gate_done=1;
            else begin awready=0;forced_result_aw_wait=forced_result_aw_wait+1;end
        end
        wready=rst_n && (wleft!=0 || (awvalid && awready && aw_count%2==0)) && ticks%6!=0;
        wlast=wleft==1;
    end
    integer f,off,bank,transfer_bank,transfer_index,transfer_offset,client;reg first_w;
    always @(posedge clk)begin
        if(!rst_n)begin rleft<=0;wleft<=0;heldar<=0;heldaw<=0;heldw<=0;heldcommit<=0;heldgrant<=0;end
        else begin
            if(core_failed || link_failed || reader_failed || arb_failed)
                $fatal(1,"core-small fault core=%h link=%h reader=%h readarb=%h",core_fault,link_fault,reader_fault,arb_fault);
            if(heldar && (!arvalid || araddr!==saved_ar || arlen!==saved_arlen))$fatal(1,"AR changed under backpressure");
            if(heldaw && (!awvalid || awaddr!==saved_aw || awlen!==saved_awlen))$fatal(1,"AW changed under backpressure");
            if(heldw && wdata!==saved_w)$fatal(1,"W data changed under backpressure");
            if(heldcommit && (!source_valid || {source_bank,source_id,source_crc,source_pixels}!==
                {saved_bank,saved_id,saved_source_crc,saved_pixels}))$fatal(1,"source commit changed while stalled");
            if(heldgrant && (!display_grant_valid || {display_base,display_crc,display_id}!==
                {saved_base,saved_display_crc,saved_display_id}))$fatal(1,"display grant changed under backpressure");
            heldar<=arvalid&&!arready;saved_ar<=araddr;saved_arlen<=arlen;
            heldaw<=awvalid&&!awready;saved_aw<=awaddr;saved_awlen<=awlen;
            heldw<=wleft!=0&&!wready;saved_w<=wdata;
            heldcommit<=source_valid&&!source_ready;saved_bank<=source_bank;saved_id<=source_id;
            saved_source_crc<=source_crc;saved_pixels<=source_pixels;
            heldgrant<=display_grant_valid&&!display_grant_ready;saved_base<=display_base;
            saved_display_crc<=display_crc;saved_display_id<=display_id;
            if(awvalid&&!awready)aw_stalls=aw_stalls+1;
            if(wleft!=0&&!wready)w_stalls=w_stalls+1;
            if(source_valid&&!source_ready)commit_stalls=commit_stalls+1;
            if(link.dma_awvalid && core_awvalid)write_contention=write_contention+1;
            if(display_valid_ar&&!display_ready_ar)display_ar_stalls=display_ar_stalls+1;
            if(source_valid)begin
                f=source_bank;
                if(source_writable[f] || !reserved[f] || source_pixels!=N || source_written[f]!=FB ||
                    source_crc!==(f ? source_crc1[0]:source_crc0[0]) || source_id!=f+1)
                    $fatal(1,"source commit is not complete/CRC-bound/reserved");
                if(wleft!=0 && wbank==f)$fatal(1,"input committed before its W drain");
            end
            if(source_valid&&source_ready)begin
                f=source_bank;starts[f]=ticks;begin_misses[f]=misses;
                if(f==0)first_start=ticks;
            end
            if(processing)begin
                f=dut.active_source;
                if(source_writable[f] || !reserved[f])$fatal(1,"processing source bank lost reservation");
                if(dut.engine.coordinate_valid&&!dut.engine.coordinate_ready)coordinate_stall[f]=coordinate_stall[f]+1;
                if(dut.engine.tone_valid&&!dut.engine.tone_ready)tone_stall[f]=tone_stall[f]+1;
                if(dut.engine.core.sampler.cache.inner.state==4)scatter_cycles[f]=scatter_cycles[f]+1;
                if(dut.engine.result_valid&&dut.engine.result_ready &&
                    (dut.engine.result_tag>=N || dut.engine.result_masked!==
                    (f ? mask1[dut.engine.result_tag]:mask0[dut.engine.result_tag])))$fatal(1,"software geometry mask mismatch");
            end
            if(arvalid&&arready)begin
                bank=araddr/STRIDE;off=araddr%STRIDE;
                if(rleft!=0 || bank>3 || off%8 || off+(arlen+1)*8>FU)$fatal(1,"physical AR out of frame");
                if(arlen==7)begin
                    if(bank>1 || !processing || bank!=dut.active_source || source_written[bank]!=FB || off%64)
                        $fatal(1,"source AR ownership/alignment/unwritten data");
                end else if(arlen==15)begin
                    if(bank<2 || !display_active || bank!=2+front_bank || result_written[bank-2]!=FB || off%128)
                        $fatal(1,"display AR ownership/alignment/unwritten result");
                end else $fatal(1,"unexpected AR length");
                rleft<=arlen+1;rindex<=bank*FB+(off>>3);rbank<=bank;
            end
            if(rvalid)begin rleft<=rleft-1;rindex<=rindex+1;end
            if(awvalid&&awready)begin
                bank=awaddr/STRIDE;off=awaddr%STRIDE;
                if(wleft!=0 || awlen!=15 || bank>3 || off%128 || off+128>FU)$fatal(1,"physical AW out of frame/burst");
                client=bank<2 ? 0:1;
                if(bank<2)begin
                    if(!reserved[bank] || (processing && dut.active_source==bank) || (source_valid&&source_bank==bank))
                        $fatal(1,"input AW writes committed/offered/free source bank");
                end else if(!processing || bank!=2+write_bank || (display_active&&write_bank==front_bank))
                    $fatal(1,"result AW writes locked/wrong bank");
                wleft<=16;windex<=bank*FB+(off>>3);wbank<=bank;aw_count=aw_count+1;
                if(wready)same_aw_w[client]=same_aw_w[client]+1;else delayed_aw_w[client]=delayed_aw_w[client]+1;
            end
            if(wready)begin
                first_w=wleft==0 && awvalid && awready;
                transfer_bank=first_w ? bank:wbank;
                transfer_index=first_w ? bank*FB+(off>>3):windex;
                transfer_offset=transfer_index-transfer_bank*FB;
                if((wleft==0&&!first_w) || wstrb!==32'hffffffff || wlast!=(!first_w&&wleft==1))
                    $fatal(1,"physical W has no owner/wrong strobes/last");
                if(transfer_bank<2)begin
                    if(!reserved[transfer_bank] || (processing&&dut.active_source==transfer_bank) ||
                        wdata!==packed_word(transfer_bank,transfer_offset,0))$fatal(1,"source RGB565 software golden mismatch");
                    source_written[transfer_bank]=source_written[transfer_bank]+1;source_checked=source_checked+1;
                end else begin
                    f=dut.active_source;
                    if(!processing || transfer_bank!=2+write_bank || wdata!==packed_word(f,transfer_offset,1))
                        $fatal(1,"corrected RGB565 software golden mismatch frame=%0d beat=%0d",f,transfer_offset);
                    result_written[transfer_bank-2]=result_written[transfer_bank-2]+1;checked=checked+1;
                end
                memory[transfer_index]<=wdata;wleft<=first_w ? 15:wleft-1;windex<=transfer_index+1;
            end
            if(rleft!=0 && wleft!=0 && rbank==wbank)$fatal(1,"physical simultaneous read/write same bank");
            if(source_released)begin
                f=released_bank;
                if((rleft!=0&&rbank==f) || (arb_busy&&arb.owner) || sample_valid ||
                    (wleft!=0&&wbank==2+write_bank) || core_awvalid || queries!=(f+1)*N || result_written[write_bank]!=FB)
                    $fatal(1,"core released source before its own read/result-write drain");
                if(dut.pending_crc!==(f ? crc1[0]:crc0[0]) || scatter_cycles[f]!=32*(misses-begin_misses[f]))
                    $fatal(1,"corrected CRC/scatter32 mismatch");
                $fdisplay(csv,"%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%08x",f,N,ticks-starts[f],last_cycles,misses-begin_misses[f],scatter_cycles[f],coordinate_stall[f],tone_stall[f],dut.pending_crc);
                $fflush(csv);
                $display("PASS actual-input core-small frame=%0d pixels=%0d CRC=%08x",f,N,dut.pending_crc);
            end
            if(fifo_push)begin
                off=read_checked%FB;
                if(fifo_data!==packed_word(read_frame,off,1))$fatal(1,"display DDR readback golden mismatch");
                read_checked=read_checked+1;
            end
        end
    end

    task automatic send_frame(input integer frame);
        integer y,x;
        begin
            wait(link.input_dma.active);repeat(8)@(negedge pix_clk);
            if(link.input_dma.active_bank!=frame)$fatal(1,"unexpected reserved input bank");
            pix_de=0;pix_vs=1;repeat(2)@(negedge pix_clk);pix_vs=0;repeat(8)@(negedge pix_clk);
            for(y=0;y<H;y=y+1)begin
                for(x=0;x<W;x=x+1)begin
                    @(negedge pix_clk);pix_de=1;pix_rgb=expand565(frame ? src1[y*W+x]:src0[y*W+x]);
                end
                @(negedge pix_clk);pix_de=0;repeat(4)@(negedge pix_clk);
            end
            repeat(3)@(negedge pix_clk);pix_vs=1;repeat(2)@(negedge pix_clk);pix_vs=0;
        end
    endtask
    integer i,frame;
    initial begin
        if(W!=32 || H!=16)$fatal(1,"core-small is fixed32x16, not a throughput run");
        $readmemh("source0.mem",src0);$readmemh("source1.mem",src1);
        $readmemh("expected0.mem",gold0);$readmemh("expected1.mem",gold1);
        $readmemh("masks0.mem",mask0);$readmemh("masks1.mem",mask1);
        $readmemh("crc0.mem",crc0);$readmemh("crc1.mem",crc1);
        $readmemh("sourcecrc0.mem",source_crc0);$readmemh("sourcecrc1.mem",source_crc1);
        for(i=0;i<2;i=i+1)begin source_written[i]=0;result_written[i]=0;starts[i]=0;begin_misses[i]=0;
            scatter_cycles[i]=0;coordinate_stall[i]=0;tone_stall[i]=0;same_aw_w[i]=0;delayed_aw_w[i]=0;end
        csv=$fopen("cycles.csv","w");
        $fdisplay(csv,"frame,pixels,small_model_cycles,processing_counter,cache_fills,scatter_cycles,coordinate_stall,tone_stall,crc32");
        repeat(12)@(negedge clk);rst_n=1;repeat(8)@(negedge pix_clk);input_enable=1;
        send_frame(0);wait(accepted==1);send_frame(1);input_enable=0;
    end
    initial begin
        wait(rst_n);
        // Force a genuine second offered commit to wait; do not invent pressure
        // requirements for the short frame's natural cache/tone behavior.
        wait(source_valid && source_bank==1);repeat(20)@(negedge clk);
        for(frame=0;frame<2;frame=frame+1)begin
            wait(pending);@(negedge clk);display_request_valid=1;
            do @(posedge clk);while(!display_request_ready);
            @(negedge clk);display_request_valid=0;
            wait(display_grant_valid);repeat(9)@(negedge clk);
            if(display_id!=frame+1 || display_base!=(2+frame)*STRIDE)$fatal(1,"wrong corrected bank/id grant");
            display_grant_ready=1;@(negedge clk);display_grant_ready=0;
            // Frame1 starts processing after the first result is granted.
            // Start display0 during its first source-read burst to exercise
            // the actual shared read arbiter without another full-frame run.
            if(frame==0)begin do @(posedge clk);while(!(sample_valid&&sample_ready));@(negedge clk);end
            read_frame=frame;reader_start=1;@(negedge clk);reader_start=0;
            wait(reader_done);@(negedge clk);
            if(read_beats!=FB || read_checked!=(frame+1)*FB || read_crc!==(frame ? crc1[0]:crc0[0]))
                $fatal(1,"complete display DDR readback count/CRC mismatch");
            repeat(20)@(negedge clk);
            if(!reader_idle || (arb_busy&&!arb.owner) || (rleft!=0&&rbank>=2))$fatal(1,"display readback not drained");
            display_done_bank=frame;display_done_valid=1;@(negedge clk);display_done_valid=0;
        end
        repeat(30)@(negedge clk);
        if(frames!=2 || accepted!=2 || queries!=2*N || source_checked!=2*FB || checked!=2*FB || read_checked!=2*FB ||
            processing || pending || display_active || display_grant_valid || source_valid || reserved!=0 || source_writable!==2'b11 ||
            link.input_dma.active || write_busy || arvalid || sample_valid || display_valid_ar || core_awvalid || awvalid ||
            rleft!=0 || wleft!=0 || arb_busy || !reader_idle || dropped!=0 || overflowed!=0 || last_drop!=0)
            $fatal(1,"core-small final ownership/DDR/input drain failed");
        if(aw_stalls==0 || w_stalls==0 || commit_stalls<20 || display_ar_stalls==0 ||
            write_contention==0 || !first_result_gate_done)
            $fatal(1,"explicit small pressure coverage missing AW=%0d W=%0d commit=%0d displayAR=%0d",aw_stalls,w_stalls,commit_stalls,display_ar_stalls);
        for(i=0;i<FB;i=i+1)begin
            if(memory[i]!==packed_word(0,i,0) || memory[FB+i]!==packed_word(1,i,0))$fatal(1,"DMA source bank was overwritten");
        end
        summary=$fopen("summary.json","w");
        $fdisplay(summary,"{\"passed\":true,\"width\":%0d,\"height\":%0d,\"frames\":2,\"source_beats\":%0d,\"result_beats\":%0d,\"readback_beats\":%0d,\"source_crc32\":[\"%08x\",\"%08x\"],\"result_crc32\":[\"%08x\",\"%08x\"],\"aw_stall\":%0d,\"w_stall\":%0d,\"commit_stall\":%0d,\"write_contention\":%0d,\"display_ar_stall\":%0d,\"same_aw_w\":[%0d,%0d],\"delayed_aw_w\":[%0d,%0d],\"capture_bursts\":%0d,\"result_bursts\":%0d,\"source_read_bursts\":%0d,\"display_read_bursts\":%0d,\"input_preloaded_not_DMA\":false,\"actual_input_DMA\":true,\"display_DDR_readback_only\":true,\"final_drain\":true,\"hardware_verified\":false,\"performance_comparable_to_full1080\":false}",W,H,source_checked,checked,read_checked,source_crc0[0],source_crc1[0],crc0[0],crc1[0],aw_stalls,w_stalls,commit_stalls,write_contention,display_ar_stalls,same_aw_w[0],same_aw_w[1],delayed_aw_w[0],delayed_aw_w[1],capture_bursts,result_bursts,source_bursts,display_bursts);
        $fclose(summary);$fclose(csv);
        $display("CORE_SMALL_FORCED_WRITE_CONTENTION selected_result_AW_wait_cycles=%0d both_client_AW_pending_cycles=%0d",forced_result_aw_wait,write_contention);
        $display("PASS actual-input core-small: two32x16 DMA-written source frames, SCATTER4 nonzero Brown software goldens, masks/CRC, two complete DDR readbacks and final ownership drain");
        $finish;
    end
endmodule
