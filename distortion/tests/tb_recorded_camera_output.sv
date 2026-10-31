`timescale 1ps/1ps
// Archival camera pixels start in modeled DDR. No camera/HDMI RX is instantiated.
// Production correction, writer, read arbiter, reader, FIFO and raster consumer
// are unmodified. This bench owns one source/result bank lease at a time.
module tb_recorded_camera_output;
    `include "config.vh"
    localparam W=VEC_WIDTH,H=VEC_HEIGHT,N=W*H,FB=N/16,FU=N/2;
    localparam STRIDE=1048576,FRAMES=2,HT=800,VT=525,HS=96,VS=2,X0=144,Y0=35;
    reg clk=0,pclk=0,rst_n=0;
    always #4000 clk=~clk;
    initial begin #1733;forever #20000 pclk=~pclk;end
    reg frame_valid=0,scan_enable=0,prepared=0;
    reg [31:0] frame_id=0;
    wire frame_ready,engine_done,engine_failed;wire [7:0] engine_fault;
    wire [1:0] gamma_mode;wire [31:0] gamma_frames,hits,misses,queries;
    wire [27:0] completed_base;wire [31:0] completed_id,completed_crc;
    wire [27:0] eng_araddr,awaddr;wire [3:0] eng_arlen,awlen;
    wire eng_arvalid,eng_arready,eng_rvalid,eng_rlast,awvalid;
    wire [3:0] eng_rid;wire [255:0] eng_rdata,wdata;wire [31:0] wstrb;
    reg awready=0,wready=0,wlast=0;
    pipeline_gamma_frame_engine_1080_core #(.WIDTH(W),.HEIGHT(H),.MAX_RADIUS_Q22(VEC_RADIUS_GUARD_Q22)) engine(
        .clk(clk),.rst_n(rst_n),.frame_valid(frame_valid),.frame_ready(frame_ready),.gamma_enable(1'b1),
        .gamma_mode(gamma_mode),.gamma_frames(gamma_frames),.source_base(28'd0),.output_base(28'd1048576),.frame_id(frame_id),
        .cfg_out_cx(VEC_OUT_CX),.cfg_out_cy(VEC_OUT_CY),.cfg_src_cx(VEC_SRC_CX),.cfg_src_cy(VEC_SRC_CY),
        .cfg_src_fx(VEC_SRC_FX),.cfg_src_fy(VEC_SRC_FY),.cfg_inv_fx(VEC_INV_FX),.cfg_inv_fy(VEC_INV_FY),
        .cfg_k1(VEC_K1),.cfg_k2(VEC_K2),.cfg_k3(VEC_K3),.cfg_p1(VEC_P1),.cfg_p2(VEC_P2),
        .araddr(eng_araddr),.arlen(eng_arlen),.arvalid(eng_arvalid),.arready(eng_arready),
        .rdata(eng_rdata),.rvalid(eng_rvalid),.rlast(eng_rlast),.rid(eng_rid),
        .awaddr(awaddr),.awlen(awlen),.awvalid(awvalid),.awready(awready),.wdata(wdata),.wstrb(wstrb),.wready(wready),.wlast(wlast),
        .done(engine_done),.failed(engine_failed),.fault(engine_fault),.completed_base(completed_base),
        .completed_id(completed_id),.completed_crc(completed_crc),.hits(hits),.misses(misses),.completed_queries(queries));
    wire [27:0] scan_araddr,araddr;wire [3:0] scan_arlen,arlen;
    wire scan_arvalid,scan_arready,scan_rvalid,scan_rlast,arvalid;wire [255:0] scan_rdata;
    wire [3:0] scan_rid;reg arready=0,rvalid=0,rlast=0;reg [255:0] rdata=0;
    wire bus_failed,bus_busy;wire [7:0] bus_fault;wire [31:0] scan_bursts,engine_bursts;
    ddr_read_arbiter read_bus(.clk(clk),.rst_n(rst_n),.display_urgent(1'b1),
        .c0_araddr(scan_araddr),.c1_araddr(eng_araddr),.c0_arlen(scan_arlen),.c1_arlen(eng_arlen),
        .c0_arvalid(scan_arvalid),.c1_arvalid(eng_arvalid),.c0_arready(scan_arready),.c1_arready(eng_arready),
        .c0_rdata(scan_rdata),.c1_rdata(eng_rdata),.c0_rvalid(scan_rvalid),.c1_rvalid(eng_rvalid),
        .c0_rlast(scan_rlast),.c1_rlast(eng_rlast),.c0_rid(scan_rid),.c1_rid(eng_rid),
        .araddr(araddr),.arlen(arlen),.arvalid(arvalid),.arready(arready),.rdata(rdata),.rvalid(rvalid),.rlast(rlast),.rid(4'd0),
        .failed(bus_failed),.fault(bus_fault),.busy(bus_busy),.bursts0(scan_bursts),.bursts1(engine_bursts));
    reg reader_start=0;wire reader_idle,reader_done,reader_failed;wire [7:0] reader_fault;
    wire [31:0] read_beats,reader_crc,reader_frames;wire fifo_wr,fifo_wr_ready,fifo_full,fifo_rd,fifo_rd_ready,fifo_valid,fifo_empty;
    wire [255:0] fifo_wdata,fifo_rdata;wire [9:0] fifo_used,fifo_available;
    ddr_video_reader #(.FRAME_BEATS(FB)) reader(.clk(clk),.rst_n(rst_n),.start(reader_start),
        .base_address(28'd1048576),.expected_checksum(completed_crc),.fifo_used(fifo_used),.fifo_ready(fifo_wr_ready),
        .fifo_wr_en(fifo_wr),.fifo_data(fifo_wdata),.araddr(scan_araddr),.arlen(scan_arlen),.arvalid(scan_arvalid),.arready(scan_arready),
        .rdata(scan_rdata),.rvalid(scan_rvalid),.rlast(scan_rlast),.rid(scan_rid),.idle(reader_idle),.done(reader_done),
        .failed(reader_failed),.fault(reader_fault),.read_beats(read_beats),.last_checksum(reader_crc),.completed_frames(reader_frames));
    video_async_fifo fifo(.wr_clk(clk),.rd_clk(pclk),.rst_n(rst_n),.wr_en(fifo_wr),.wr_data(fifo_wdata),
        .wr_full(fifo_full),.wr_ready(fifo_wr_ready),.rd_en(fifo_rd),.rd_data(fifo_rdata),.rd_valid(fifo_valid),
        .rd_empty(fifo_empty),.rd_ready(fifo_rd_ready),.rd_available(fifo_available),.wr_used(fifo_used));
    wire request_toggle,grant_ack,done_toggle,done_good,done_bank,frame_active,pix_start,pix_last,pix_valid,pix_bank;
    wire [31:0] request_epoch,done_epoch,done_id,done_crc,consumed,pix_id,scan_frames,underflows,mismatches;
    reg grant_toggle=0,grant_valid=0,done_ack=0;reg [31:0] grant_epoch=0,grant_id=0,grant_crc=0;
    wire hs,vs,de,display_valid,pixel_failed,draining;wire [7:0] rr,gg,bb,pixel_fault;
    ddr_video_output_1080_board #(.WIDTH(W),.HEIGHT(H),.HT(HT),.VT(VT),.HS(HS),.VS(VS),.X0(X0),.Y0(Y0),.AW(W),.AH(H)) scan(
        .clk(pclk),.rst_n(rst_n),.enable(scan_enable),.abort(1'b0),.abort_fault(8'd0),
        .request_toggle(request_toggle),.request_epoch(request_epoch),.grant_toggle(grant_toggle),.grant_valid(grant_valid),
        .grant_epoch(grant_epoch),.grant_checksum(grant_crc),.grant_id(grant_id),.grant_bank(1'b0),.grant_ack_toggle(grant_ack),.done_ack_toggle(done_ack),
        .fifo_ready(fifo_rd_ready),.fifo_valid(fifo_valid),.fifo_data(fifo_rdata),.fifo_rd_en(fifo_rd),
        .hs(hs),.vs(vs),.de(de),.r(rr),.g(gg),.b(bb),.display_valid(display_valid),
        .done_toggle(done_toggle),.done_good(done_good),.done_epoch(done_epoch),.done_id(done_id),.done_crc(done_crc),.done_bank(done_bank),
        .consumed_pixels(consumed),.frame_active(frame_active),.active_id(pix_id),.active_bank(pix_bank),
        .frame_start(pix_start),.frame_last(pix_last),.pixel_valid(pix_valid),.failed(pixel_failed),.fault(pixel_fault),
        .draining(draining),.completed_frames(scan_frames),.underflows(underflows),.mismatches(mismatches));
    reg [255:0] source_words[0:FRAMES*FB-1],memory_source[0:FB-1],memory_result[0:FB-1];
    reg [15:0] golden[0:FRAMES*N-1];reg [31:0] source_crcs[0:FRAMES-1],expected_crcs[0:FRAMES-1];
    integer current=-1,ticks=0,rleft=0,rindex=0,rkind=0,wleft=0,windex=0;
    integer written=0,total_written=0,total_readback=0,aw_stalls=0,w_stalls=0,ar_stalls=0,peak_fifo=0;
    reg held_aw=0,held_ar=0,held_w=0;reg [27:0] saved_aw=0,saved_ar=0;reg [3:0] saved_arlen=0;reg [255:0] saved_w=0;
    integer i,j,f,rows,pixels_file,summary,start_tick,finish_tick;
    reg [31:0] source_crc;reg [255:0] expected_word;
    function automatic [31:0] crc_byte(input [31:0] old,input [7:0] b);
        reg [31:0] c;integer bitno;begin c=old^b;for(bitno=0;bitno<8;bitno=bitno+1)c=c[0] ? (c>>1)^32'hedb88320:c>>1;crc_byte=c;end
    endfunction
    function automatic [23:0] expand565(input [15:0] p);
        expand565={p[15:11],p[15:13],p[10:5],p[10:9],p[4:0],p[4:2]};
    endfunction
    always @(negedge clk)begin
        ticks=ticks+1;if(ticks>20000000)$fatal(1,"bounded replay exceeded20M core cycles");
        if(rst_n&&ticks%1000000==0)$display("REPLAY_PROGRESS frame=%0d tick=%0d written=%0d scan=%0d fifo=%0d",frame_id,ticks,written,scan_frames,fifo_used);
        arready=rst_n&&rleft==0&&ticks%7>=2;
        rvalid=rst_n&&rleft>0&&ticks%5!=0;rlast=rleft==1;
        if(rvalid)rdata=rkind==0 ? memory_source[rindex]:memory_result[rindex];
        awready=rst_n&&wleft==0&&ticks%9>=3;
        wready=rst_n&&wleft>0&&ticks%6!=0;wlast=wleft==1;
    end
    always @(posedge clk)begin
        if(rst_n)begin
            if(engine_failed||reader_failed||bus_failed||pixel_failed)$fatal(1,"production block fault engine=%h reader=%h bus=%h scan=%h",engine_fault,reader_fault,bus_fault,pixel_fault);
            if(held_aw&&(!awvalid||awaddr!==saved_aw))$fatal(1,"AW changed while stalled");
            if(held_ar&&(!arvalid||araddr!==saved_ar||arlen!==saved_arlen))$fatal(1,"AR changed while stalled");
            if(held_w&&wdata!==saved_w)$fatal(1,"W payload changed while stalled");
            held_aw=awvalid&&!awready;saved_aw=awaddr;held_ar=arvalid&&!arready;saved_ar=araddr;saved_arlen=arlen;
            held_w=wleft>0&&!wready;saved_w=wdata;
            if(held_aw)aw_stalls=aw_stalls+1;if(held_ar)ar_stalls=ar_stalls+1;if(held_w)w_stalls=w_stalls+1;
            if(fifo_used>peak_fifo)peak_fifo=fifo_used;
            if(arvalid&&arready)begin
                if(rleft!=0||araddr[2:0]!=0)$fatal(1,"overlapping/unaligned modeled DDR read");
                if(araddr<FU)begin rkind=0;rindex=araddr/8;if(arlen!=7||prepared)$fatal(1,"source lease read after processing completion");end
                else if(araddr>=STRIDE&&araddr<STRIDE+FU)begin rkind=1;rindex=(araddr-STRIDE)/8;if(arlen!=15||!prepared)$fatal(1,"display read before full result publication");end
                else $fatal(1,"read outside owned source/result regions");
                if(rindex+arlen>=FB)$fatal(1,"read burst crosses frame boundary");rleft=arlen+1;
            end
            if(rvalid)begin
                if(rleft<=0)$fatal(1,"unsolicited modeled DDR response");
                if(rkind==1)total_readback=total_readback+1;rleft=rleft-1;rindex=rindex+1;
            end
            if(awvalid&&awready)begin
                if(prepared||awlen!=15||awaddr!=STRIDE+written*8||wleft!=0)$fatal(1,"result burst outside processing lease/order");
                wleft=16;windex=(awaddr-STRIDE)/8;
            end
            if(wready)begin
                if(wleft<=0||wstrb!==32'hffffffff)$fatal(1,"invalid result write/mask");
                for(j=0;j<16;j=j+1)expected_word[j*16+:16]=golden[current*N+windex*16+j];
                if(wdata!==expected_word)$fatal(1,"processed DDR pixel differs from independent golden frame=%0d beat=%0d",frame_id,windex);
                memory_result[windex]=wdata;windex=windex+1;wleft=wleft-1;written=written+1;total_written=total_written+1;
            end
        end
    end
    // Explicit held-bundle parent protocol; never force production bank state.
    reg [1:0] request_sync=0,done_sync=0,ack_sync=0;reg request_seen=0,done_seen=0;
    reg lease=0,reader_finished=0,pixels_finished=0;integer releases=0;reg [31:0] lease_epoch=0;
    always @(posedge clk)begin
        if(!rst_n)begin request_sync<=0;done_sync<=0;ack_sync<=0;end
        else begin
            request_sync<={request_sync[0],request_toggle};done_sync<={done_sync[0],done_toggle};ack_sync<={ack_sync[0],grant_ack};
            reader_start<=0;
            if(request_sync[1]!=request_seen)begin
                request_seen<=request_sync[1];
                if(lease||grant_toggle!=ack_sync[1])$fatal(1,"new scan request before prior lease/held grant drained");
                grant_epoch<=request_epoch;grant_toggle<=!grant_toggle;grant_valid<=prepared;
                if(prepared)begin
                    if(!reader_idle||fifo_used!=0||fifo_available!=0)$fatal(1,"grant before reader/FIFO empty");
                    grant_id<=completed_id;grant_crc<=completed_crc;lease_epoch<=request_epoch;
                    lease<=1;reader_finished<=0;pixels_finished<=0;reader_start<=1;
                end
            end
            if(reader_done)begin
                if(!lease||reader_crc!==expected_crcs[current]||read_beats!=FB)$fatal(1,"reader CRC/count does not support current lease");
                reader_finished<=1;
            end
            if(done_sync[1]!=done_seen)begin
                done_seen<=done_sync[1];
                if(!lease||!done_good||done_id!=frame_id||done_bank!=0||done_epoch!=lease_epoch||done_crc!==expected_crcs[current]||consumed!=N)
                    $fatal(1,"pixel completion ID/bank/epoch/CRC/count differs");
                pixels_finished<=1;
            end
            if(lease&&reader_finished&&pixels_finished&&reader_idle&&!bus_busy&&rleft==0&&fifo_used==0&&fifo_available==0&&!fifo_valid)begin
                if(scan.frame_active||scan.queued!=0||scan.inflight!=0||pixel_failed||reader_failed)$fatal(1,"bank release before actual scan/transaction drain");
                lease<=0;releases<=releases+1;done_ack<=done_sync[1];
            end
        end
    end
    integer output_tick=0,origin_tick=0,out_x=0,out_y=0,scan_count=0,scan_start_tick=0,total_pixels=0;
    reg raster_seen=0,previous_vs=0;reg [31:0] pixel_crc=32'hffffffff;reg [15:0] observed;
    always @(posedge pclk)begin
        if(rst_n)begin
            #1;output_tick=output_tick+1;
            if(vs&&!previous_vs)begin
                if(raster_seen&&output_tick-origin_tick!=HT*VT)$fatal(1,"output raster period changed");
                origin_tick=output_tick;raster_seen=1;
            end
            previous_vs=vs;
            if(raster_seen)begin
                out_x=(output_tick-origin_tick)%HT;out_y=((output_tick-origin_tick)/HT)%VT;
                if(hs!==(out_x<HS)||vs!==(out_y<VS)||de!==(out_x>=X0&&out_x<X0+W&&out_y>=Y0&&out_y<Y0+H))$fatal(1,"registered HS/VS/DE differs");
            end
            if(pix_valid)begin
                if(!de||!lease||pix_id!=frame_id||pix_bank!=0)$fatal(1,"output pixel outside current granted epoch");
                if(pix_start)begin
                    if(out_x!=X0||out_y!=Y0)$fatal(1,"scan did not begin at ROI origin");
                    scan_count=0;pixel_crc=32'hffffffff;scan_start_tick=output_tick;
                end
                if(scan_count>=N||output_tick-scan_start_tick!=(scan_count/W)*HT+scan_count%W)$fatal(1,"output pixel cadence/count differs");
                if({rr,gg,bb}!==expand565(golden[current*N+scan_count]))$fatal(1,"actual DE/RGB mismatch frame=%0d pixel=%0d got=%h expected=%h",frame_id,scan_count,{rr,gg,bb},expand565(golden[current*N+scan_count]));
                observed={rr[7:3],gg[7:2],bb[7:3]};$fdisplay(pixels_file,"%04x",observed);
                pixel_crc=crc_byte(crc_byte(pixel_crc,observed[7:0]),observed[15:8]);scan_count=scan_count+1;total_pixels=total_pixels+1;
                if(pix_last&&(scan_count!=N||~pixel_crc!==expected_crcs[current]))$fatal(1,"last scanned pixel/CPU CRC differs");
            end else if({rr,gg,bb}!==0)$fatal(1,"inactive raster is not black");
        end
    end
    initial begin
        if(W!=640||H!=480)$fatal(1,"this archival full-frame regression is640x480 only");
        $readmemh("source0.mem",source_words,0,FB-1);$readmemh("source1.mem",source_words,FB,2*FB-1);
        $readmemh("expected0.mem",golden,0,N-1);$readmemh("expected1.mem",golden,N,2*N-1);
        $readmemh("source-crcs.mem",source_crcs);$readmemh("expected-crcs.mem",expected_crcs);
        rows=$fopen("frames.csv","w");pixels_file=$fopen("scan-pixels.mem","w");
        $fdisplay(rows,"frame_id,source_epoch,result_epoch,source_bank,result_bank,pixels,result_beats,start_cycle,process_done_cycle,release_cycle,source_crc32,result_crc32,reader_crc32,scan_crc32,request_epoch");
        repeat(12)@(negedge clk);rst_n=1;repeat(12)@(negedge clk);
        for(f=0;f<FRAMES;f=f+1)begin
            if(lease||wleft!=0||rleft!=0||!reader_idle||fifo_used!=0)$fatal(1,"source/result bank reuse before release");
            current=f;frame_id=f+1;written=0;prepared=0;
            for(i=0;i<FB;i=i+1)begin memory_source[i]=source_words[f*FB+i];memory_result[i]=256'hdeadbeef;end
            wait(frame_ready);@(negedge clk);start_tick=ticks;frame_valid=1;@(negedge clk);frame_valid=0;
            wait(engine_done);@(negedge clk);finish_tick=ticks;
            if(completed_id!=frame_id||completed_base!=STRIDE||completed_crc!==expected_crcs[f]||written!=FB||wleft!=0||queries!=(f+1)*N||gamma_frames!=f+1)$fatal(1,"full processed frame metadata/count/CRC differs");
            source_crc=32'hffffffff;
            for(i=0;i<FB;i=i+1)begin
                if(memory_source[i]!==source_words[f*FB+i])$fatal(1,"immutable source changed during processing");
                for(j=0;j<32;j=j+1)source_crc=crc_byte(source_crc,memory_source[i][j*8+:8]);
            end
            if(~source_crc!==source_crcs[f])$fatal(1,"source CRC differs from archival camera capture");
            prepared=1;scan_enable=1;wait(releases==f+1);@(negedge clk);scan_enable=0;prepared=0;
            repeat(30)@(negedge clk);
            if(lease||fifo_used!=0||fifo_available!=0||!fifo_empty||fifo_valid||scan.queued!=0||scan.inflight!=0||scan.done_pending||!reader_idle||bus_busy||rleft!=0||wleft!=0||underflows||mismatches)$fatal(1,"final source/result/read/FIFO/raster ownership did not drain");
            $fdisplay(rows,"%0d,%0d,%0d,0,0,%0d,%0d,%0d,%0d,%0d,%08x,%08x,%08x,%08x,%0d",frame_id,frame_id,frame_id,N,written,start_tick,finish_tick,ticks,~source_crc,completed_crc,reader_crc,~pixel_crc,lease_epoch);$fflush(rows);
            $display("REPLAY_FRAME_PASS id=%0d source=%08x result=%08x process_cycles=%0d release_cycle=%0d",frame_id,~source_crc,completed_crc,finish_tick-start_tick,ticks);
        end
        if(total_pixels!=FRAMES*N||total_written!=FRAMES*FB||total_readback!=FRAMES*FB||scan_frames!=FRAMES||reader_frames!=FRAMES||releases!=FRAMES||aw_stalls==0||w_stalls==0||ar_stalls==0||peak_fifo==0)$fatal(1,"all-frame scan/drain/pressure coverage differs");
        $fclose(pixels_file);$fclose(rows);summary=$fopen("summary.json","w");
        $fdisplay(summary,"{\"passed\":true,\"frames_processed\":%0d,\"frames_unique_scanned\":%0d,\"pixels_compared\":%0d,\"source_bank_reuses\":1,\"result_bank_reuses\":1,\"bank_releases\":%0d,\"result_beats\":%0d,\"display_read_beats\":%0d,\"underflows\":%0d,\"crc_mismatches\":%0d,\"aw_stall_cycles\":%0d,\"w_stall_cycles\":%0d,\"ar_stall_cycles\":%0d,\"fifo_peak\":%0d,\"final_drain\":true}",FRAMES,scan_frames,total_pixels,releases,total_written,total_readback,underflows,mismatches,aw_stalls,w_stalls,ar_stalls,peak_fifo);$fclose(summary);
        $display("PASS recorded camera output: full640x480 archival camera frames, independent Brown/bilinear/Gamma pixels, result DDR, real reader/FIFO, actual DE/RGB scan, reused-bank epochs and final drain");$finish;
    end
endmodule
