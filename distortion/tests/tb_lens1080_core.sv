`timescale 1ns/1ps
module tb_lens1080_core;
    `include "config.vh"
    localparam W=VEC_WIDTH,H=VEC_HEIGHT,N=W*H,FB=N/16,FU=N/2;
    localparam STRIDE=1048576,BANK_BEATS=STRIDE/8,MAX_CYCLES=80000000;
    reg clk=0;always #4 clk=~clk;
    reg rst_n=0,source_valid=0,source_bank=0;wire source_ready;
    reg [31:0] source_id=0;wire [1:0] source_writable;
    wire source_released,released_bank;
    reg display_request_valid=0,display_grant_ready=0,display_done_valid=0,display_done_bank=0;
    wire display_request_ready,display_grant_valid;
    wire [27:0] display_base;wire [31:0] display_crc,display_id;
    reg signed [23:0] cx=VEC_SRC_CX;reg signed [31:0] k1=VEC_K1;
    wire processing,pending,display_active,write_bank,front_bank,failed;
    wire [7:0] fault;wire [31:0] frames,last_cycles,hits,misses,queries;
    wire [27:0] sample_ar,awaddr;wire [3:0] sample_len,awlen;
    wire sample_valid,sample_ready,awvalid;reg awready=0,wready=0,wlast=0;
    wire [255:0] sample_data,wdata;wire sample_rvalid,sample_last;wire [3:0] sample_id;
    wire [31:0] wstrb;
    lens1080_bank_core #(.WIDTH(W),.HEIGHT(H),.BANK_STRIDE(STRIDE),.MAX_RADIUS_Q22(VEC_RADIUS_GUARD_Q22)) dut(
        .clk(clk),.rst_n(rst_n),.source_valid(source_valid),.source_ready(source_ready),.source_bank(source_bank),.source_id(source_id),
        .source_writable(source_writable),.source_released(source_released),.released_bank(released_bank),
        .display_request_valid(display_request_valid),.display_request_ready(display_request_ready),
        .display_grant_valid(display_grant_valid),.display_grant_ready(display_grant_ready),
        .display_base(display_base),.display_crc(display_crc),.display_id(display_id),
        .display_done_valid(display_done_valid),.display_done_bank(display_done_bank),
        .cfg_out_cx(VEC_OUT_CX),.cfg_out_cy(VEC_OUT_CY),.cfg_src_cx(cx),.cfg_src_cy(VEC_SRC_CY),
        .cfg_src_fx(VEC_SRC_FX),.cfg_src_fy(VEC_SRC_FY),.cfg_inv_fx(VEC_INV_FX),.cfg_inv_fy(VEC_INV_FY),
        .cfg_k1(k1),.cfg_k2(VEC_K2),.cfg_k3(VEC_K3),.cfg_p1(VEC_P1),.cfg_p2(VEC_P2),
        .araddr(sample_ar),.arlen(sample_len),.arvalid(sample_valid),.arready(sample_ready),
        .rdata(sample_data),.rvalid(sample_rvalid),.rlast(sample_last),.rid(sample_id),
        .awaddr(awaddr),.awlen(awlen),.awvalid(awvalid),.awready(awready),.wdata(wdata),.wstrb(wstrb),.wready(wready),.wlast(wlast),
        .processing(processing),.pending(pending),.display_active(display_active),.write_bank(write_bank),.front_bank(front_bank),
        .completed_frames(frames),.last_cycles(last_cycles),.hits(hits),.misses(misses),.queries(queries),.failed(failed),.fault(fault));
    reg reader_start=0;wire reader_idle,reader_done,reader_failed;wire [7:0] reader_fault;
    wire [27:0] display_ar;wire [3:0] display_len;wire display_valid_ar,display_ready_ar;
    wire [255:0] display_data;wire display_rvalid,display_last;wire [3:0] display_rid;
    wire fifo_push;wire [255:0] fifo_data;wire [31:0] read_beats,read_crc,read_frames;
    integer ticks=0;
    wire [9:0] fake_fifo_used=(ticks%127<8) ? 10'd500:10'd0;
    ddr_video_reader #(.FRAME_BEATS(FB)) reader(.clk(clk),.rst_n(rst_n),.start(reader_start),
        .base_address(display_base),.expected_checksum(display_crc),.fifo_used(fake_fifo_used),.fifo_ready(1'b1),
        .fifo_wr_en(fifo_push),.fifo_data(fifo_data),.araddr(display_ar),.arlen(display_len),.arvalid(display_valid_ar),.arready(display_ready_ar),
        .rdata(display_data),.rvalid(display_rvalid),.rlast(display_last),.rid(display_rid),.idle(reader_idle),.done(reader_done),
        .failed(reader_failed),.fault(reader_fault),.read_beats(read_beats),.last_checksum(read_crc),.completed_frames(read_frames));
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
    reg [255:0] memory[0:4*BANK_BEATS-1];
    reg [15:0] src0[0:N-1],src1[0:N-1],gold0[0:N-1],gold1[0:N-1];
    reg mask0[0:N-1],mask1[0:N-1];reg [31:0] crc0[0:0],crc1[0:0];
    integer rleft=0,rindex=0,wleft=0,windex=0,checked=0,read_checked=0;
    integer read_frame=0,output_read_frames=0;
    integer starts[0:1],begin_hits[0:1],begin_misses[0:1],begin_reads[0:1],begin_writes[0:1];
    integer coordinate_stall[0:1],tone_stall[0:1],scatter_cycles[0:1],ar_stall[0:1],aw_stall[0:1],w_stall[0:1];
    integer csv,summary,first_start=0,last_end=0;
    reg heldar=0,heldaw=0,heldw=0,heldtone=0,heldgrant=0;
    reg [27:0] saved_ar,saved_aw,saved_base;reg [3:0] saved_arlen,saved_awlen;
    reg [255:0] saved_w;reg [15:0] saved_tone;reg [23:0] saved_tag;
    reg [31:0] saved_crc,saved_id;
    reg source_held=0,saved_source_bank;reg [31:0] saved_source_id;
    integer source_commit_stall=0;
    function automatic [255:0] packed_word(input integer frame,input integer offset,input integer kind);
        integer j;begin
            for(j=0;j<16;j=j+1) begin
                if(kind==0) packed_word[j*16+:16]=frame==0 ? src0[offset*16+j]:src1[offset*16+j];
                else packed_word[j*16+:16]=frame==0 ? gold0[offset*16+j]:gold1[offset*16+j];
            end
        end
    endfunction
    always @(negedge clk) begin
        ticks=ticks+1;
        if(ticks>MAX_CYCLES)$fatal(1,"bounded core simulation cycle timeout");
        arready=rst_n && rleft==0 && ticks%7>=2;
        awready=rst_n && wleft==0 && ticks%9>=3;
        rvalid=rst_n && rleft!=0 && ticks%5!=0;rlast=rleft==1;
        if(rvalid)rdata=memory[rindex];
        wready=rst_n && wleft!=0 && ticks%6!=0;wlast=wleft==1;
    end
    integer f,off,bank;
    always @(posedge clk) begin
        if(!rst_n) begin rleft<=0;wleft<=0;heldar<=0;heldaw<=0;heldw<=0;heldtone<=0;heldgrant<=0;end
        else begin
            if(failed || reader_failed || arb_failed)$fatal(1,"core/read fault=%h reader=%h arb=%h",fault,reader_fault,arb_fault);
            if(heldar && (!arvalid || araddr!==saved_ar || arlen!==saved_arlen))$fatal(1,"AR changed under backpressure");
            if(heldaw && (!awvalid || awaddr!==saved_aw || awlen!==saved_awlen))$fatal(1,"AW changed under backpressure");
            if(heldw && wdata!==saved_w)$fatal(1,"W changed under backpressure");
            if(heldtone && (!dut.engine.tone_valid || dut.engine.tone_pixel!==saved_tone || dut.engine.tone_tag!==saved_tag))$fatal(1,"tone/tag changed while stalled");
            if(heldgrant && (!display_grant_valid || display_base!==saved_base || display_crc!==saved_crc || display_id!==saved_id))$fatal(1,"display grant changed while stalled");
            heldar<=arvalid&&!arready;saved_ar<=araddr;saved_arlen<=arlen;
            heldaw<=awvalid&&!awready;saved_aw<=awaddr;saved_awlen<=awlen;
            heldw<=wleft!=0&&!wready;saved_w<=wdata;
            heldtone<=dut.engine.tone_valid&&!dut.engine.tone_ready;saved_tone<=dut.engine.tone_pixel;saved_tag<=dut.engine.tone_tag;
            heldgrant<=display_grant_valid&&!display_grant_ready;saved_base<=display_base;saved_crc<=display_crc;saved_id<=display_id;
            if(source_held && (!source_valid || source_bank!==saved_source_bank || source_id!==saved_source_id))$fatal(1,"source commit changed while stalled");
            source_held<=source_valid&&!source_ready;saved_source_bank<=source_bank;saved_source_id<=source_id;
            if(source_valid && source_writable[source_bank])$fatal(1,"offered source bank exposed writable");
            if(source_valid&&!source_ready)source_commit_stall=source_commit_stall+1;
            if(source_valid && source_ready) begin
                f=source_bank;starts[f]=ticks;begin_hits[f]=hits;begin_misses[f]=misses;begin_reads[f]=source_bursts;begin_writes[f]=checked;
                if(f==0)first_start=ticks;
            end
            if(processing) begin
                f=dut.active_source;
                if(source_writable[f])$fatal(1,"active source exposed writable");
                if(dut.engine.coordinate_valid&&!dut.engine.coordinate_ready)coordinate_stall[f]=coordinate_stall[f]+1;
                if(dut.engine.tone_valid&&!dut.engine.tone_ready)tone_stall[f]=tone_stall[f]+1;
                if(dut.engine.core.sampler.cache.inner.state==4)scatter_cycles[f]=scatter_cycles[f]+1;
                if(sample_valid&&!sample_ready)ar_stall[f]=ar_stall[f]+1;
                if(awvalid&&!awready)aw_stall[f]=aw_stall[f]+1;
                if(wleft!=0&&!wready)w_stall[f]=w_stall[f]+1;
                if(dut.engine.result_valid&&dut.engine.result_ready)begin
                    if(dut.engine.result_tag>=N)$fatal(1,"tag outside native frame");
                    if(dut.engine.result_masked!==(f ? mask1[dut.engine.result_tag]:mask0[dut.engine.result_tag]))$fatal(1,"independent geometry mask mismatch");
                end
            end
            if(arvalid&&arready) begin
                bank=araddr/STRIDE;off=araddr%STRIDE;
                if(rleft!=0 || bank<0 || bank>3 || off+(arlen+1)*8>FU)$fatal(1,"AR bank overlap/outside frame");
                if(arlen==7)begin
                    if(bank>1 || bank!=dut.active_source || !processing || off%64)$fatal(1,"source AR ownership/alignment");
                end else if(arlen==15)begin
                    if(bank<2 || bank!=2+front_bank || !display_active || off%128)$fatal(1,"display AR ownership/alignment");
                end else $fatal(1,"unexpected read burst length");
                rleft<=arlen+1;rindex<=araddr>>3;
            end
            if(rvalid)begin rleft<=rleft-1;rindex<=rindex+1;end
            if(awvalid&&awready)begin
                bank=awaddr/STRIDE;off=awaddr%STRIDE;
                if(wleft!=0 || awlen!=15 || off%128 || off+128>FU || bank!=2+write_bank || !processing)$fatal(1,"AW overlap/layout/ownership");
                if(display_active&&write_bank==front_bank)$fatal(1,"write locked display bank");
                wleft<=16;windex<=awaddr>>3;
            end
            if(wready)begin
                f=dut.active_source;off=windex-(2+write_bank)*BANK_BEATS;
                if(off<0 || off>=FB || wstrb!==32'hffffffff || wdata!==packed_word(f,off,1))$fatal(1,"full-frame integer golden mismatch frame=%0d beat=%0d actual=%h expected=%h",f,off,wdata,packed_word(f,off,1));
                memory[windex]<=wdata;wleft<=wleft-1;windex<=windex+1;checked<=checked+1;
                if(checked%4096==4095)$display("core progress frame=%0d output_pixels=%0d tick=%0d",f,(off+1)*16,ticks);
            end
            if(rleft!=0&&wleft!=0&&rindex/BANK_BEATS==windex/BANK_BEATS)$fatal(1,"concurrent read/write same bank");
            if(source_released) begin
                f=released_bank;
                if(wleft!=0 || rleft!=0 || arb_busy || queries!=(f+1)*N || checked-begin_writes[f]!=FB)$fatal(1,"publish before full drain/query count");
                if(dut.pending_crc!==(f ? crc1[0]:crc0[0]))$fatal(1,"result CRC mismatch");
                $fdisplay(csv,"%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%08x",f,N,2*N,ticks-starts[f],last_cycles,hits-begin_hits[f],misses-begin_misses[f],source_bursts-begin_reads[f],checked-begin_writes[f],coordinate_stall[f],tone_stall[f],scatter_cycles[f],ar_stall[f],aw_stall[f],w_stall[f],dut.pending_crc);
                $fflush(csv);
                $display("PASS core frame %0d pixels=%0d cycles=%0d misses=%0d crc=%08x",f,N,ticks-starts[f],misses-begin_misses[f],dut.pending_crc);
            end
            if(fifo_push) begin
                off=read_checked%FB;
                if(fifo_data!==packed_word(read_frame,off,1))$fatal(1,"full display readback differs frame=%0d beat=%0d",read_frame,off);
                read_checked<=read_checked+1;
            end
        end
    end
    task automatic commit(input integer frame);
        begin
            @(negedge clk);
            if(!source_writable[frame])$fatal(1,"producer offered a nonfree source bank");
            cx=VEC_SRC_CX;k1=VEC_K1;source_bank=frame;source_id=100+frame;source_valid=1;
            do @(posedge clk);while(!source_ready);
            @(negedge clk);source_valid=0;
            repeat(8)@(negedge clk);cx=0;k1=0; // accepted configuration must remain locked
        end
    endtask
    integer i,j;
    initial begin
        $readmemh("source0.mem",src0);$readmemh("source1.mem",src1);$readmemh("expected0.mem",gold0);$readmemh("expected1.mem",gold1);
        $readmemh("masks0.mem",mask0);$readmemh("masks1.mem",mask1);$readmemh("crc0.mem",crc0);$readmemh("crc1.mem",crc1);
        for(i=0;i<FB;i=i+1)begin memory[i]=packed_word(0,i,0);memory[BANK_BEATS+i]=packed_word(1,i,0);end
        for(i=0;i<2;i=i+1)begin coordinate_stall[i]=0;tone_stall[i]=0;scatter_cycles[i]=0;ar_stall[i]=0;aw_stall[i]=0;w_stall[i]=0;end
        csv=$fopen("cycles.csv","w");$fdisplay(csv,"frame,pixels,bytes,total_cycles,processing_counter,cache_hits,cache_fills,source_read_bursts,written_beats,coordinate_stall,tone_stall,scatter_cycles,source_ar_stall,aw_stall,w_stall,crc32");
        repeat(12)@(negedge clk);rst_n=1;
        commit(0);commit(1); // offer next bank early and hold through backpressure
    end
    integer frame;
    initial begin
        wait(rst_n);
        for(frame=0;frame<2;frame=frame+1)begin
            // A refresh request without pending is allowed to repeat front.
            // This task requests each NEW result once, rather than a refresh.
            if(frame!=0)wait(pending);
            @(negedge clk);display_request_valid=1;
            do @(posedge clk);while(!display_request_ready);
            @(negedge clk);display_request_valid=0;
            wait(display_grant_valid);repeat(9)@(negedge clk);
            if(display_id!=100+frame || display_base!=(2+frame)*STRIDE)$fatal(1,"wrong frame/bank published");
            read_frame=frame;reader_start=1;display_grant_ready=1;
            @(negedge clk);reader_start=0;display_grant_ready=0;
            wait(reader_done);@(negedge clk);
            if(read_beats!=FB || read_checked!=(frame+1)*FB || read_crc!==(frame ? crc1[0]:crc0[0]))$fatal(1,"display native count/CRC/drain mismatch");
            repeat(40)@(negedge clk);
            if(!reader_idle || rleft!=0 || arb_busy)$fatal(1,"readback not drained before bank release");
            display_done_bank=frame;display_done_valid=1;
            @(negedge clk);display_done_valid=0;output_read_frames=output_read_frames+1;
        end
        repeat(30)@(negedge clk);last_end=ticks;
        if(frames!=2 || queries!=2*N || checked!=2*FB || read_checked!=2*FB || processing || pending || display_active || display_grant_valid || source_commit_stall==0)$fatal(1,"final frame state not drained/backpressured");
        for(i=0;i<FB;i=i+1)begin
            if(memory[i]!==packed_word(0,i,0) || memory[BANK_BEATS+i]!==packed_word(1,i,0))$fatal(1,"source frame overwritten");
        end
        summary=$fopen("summary.json","w");
        $fdisplay(summary,"{\"passed\":true,\"width\":%0d,\"height\":%0d,\"frames\":2,\"pixels_per_frame\":%0d,\"bytes_per_frame\":%0d,\"beats_per_frame\":%0d,\"total_cycles\":%0d,\"result_beats\":%0d,\"readback_beats\":%0d,\"source_read_bursts\":%0d,\"display_read_bursts\":%0d,\"bank_stride_units\":%0d,\"bank_stride_bytes\":%0d,\"core_clock_target_hz\":125000000,\"input_preloaded_not_DMA\":true,\"synthetic_model\":true,\"hardware_verified\":false}",W,H,N,2*N,FB,last_end-first_start,checked,read_checked,source_bursts,display_bursts,STRIDE,STRIDE*4);
        $fclose(summary);$fclose(csv);
        $display("PASS native1080 core: %0dx%0d two full frames, nonzero synthetic Brown, exact pixels/mask/CRC, four-bank ownership, DDR stalls, GM0 and full readback. cycles=%0d",W,H,last_end-first_start);$finish;
    end
endmodule
