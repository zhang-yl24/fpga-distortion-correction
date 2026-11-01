`timescale 1ps/1ps
// Synthetic source frames start in modeled DDR. The production bank manager,
// nonlinear mapper, result writer, read arbiter, reader, FIFO and scan are real.
// Sensor/DVP, physical DDR and the board top are deliberately outside this test.
module tb_camera720_output;
    `include "config.vh"
    localparam W=1280,H=720,N=W*H,FB=N/16,FU=N/2,STRIDE=1048576,FRAMES=3;
    localparam OW=1920,OH=1080,HT=2200,VT=1125,HS=44,VS=5,X0=192,Y0=41;
    localparam WX=X0+(OW-W)/2,WY=Y0+(OH-H)/2;
    reg clk=0,pclk=0,rst_n=1;
    initial begin #1;rst_n=0;end
    always #4000 clk=~clk;
    // Rational half-period: 1e12 / (2 * 74.25e6) ps, no accumulated rounding.
    integer clock_phase=0,clock_delay;
    initial begin #1733;forever begin
        clock_phase=clock_phase+2000000;clock_delay=clock_phase/297;
        clock_phase=clock_phase%297;#(clock_delay)pclk=~pclk;
    end end
    reg source_valid=0,source_bank=0;reg [31:0] source_id=0;
    wire source_ready,source_released,released_bank;wire [1:0] source_writable;
    reg display_request=0,display_grant_ready=0,display_done=0,display_done_bank=0;
    wire display_ready,display_grant_valid,processing,pending,display_active,write_bank,front_bank;
    wire [27:0] display_base;wire [31:0] display_crc,display_id,processed,last_cycles,hits,misses,queries;
    wire bank_failed;wire [7:0] bank_fault;
    wire [27:0] eng_araddr,awaddr;wire [3:0] eng_arlen,awlen;
    wire eng_arvalid,eng_arready,eng_rvalid,eng_rlast,awvalid;
    wire [3:0] eng_rid;wire [255:0] eng_rdata,wdata;wire [31:0] wstrb;
    reg awready=0,wready=0,wlast=0;
    lens1080_bank_core #(.WIDTH(W),.HEIGHT(H),.BANK_STRIDE(STRIDE),.MAX_RADIUS_Q22(VEC_RADIUS_GUARD_Q22)) bank_core(
        .clk(clk),.rst_n(rst_n),.source_valid(source_valid),.source_ready(source_ready),.source_bank(source_bank),.source_id(source_id),
        .source_writable(source_writable),.source_released(source_released),.released_bank(released_bank),
        .display_request_valid(display_request),.display_request_ready(display_ready),
        .display_grant_valid(display_grant_valid),.display_grant_ready(display_grant_ready),
        .display_base(display_base),.display_crc(display_crc),.display_id(display_id),
        .display_done_valid(display_done),.display_done_bank(display_done_bank),
        .cfg_out_cx(VEC_OUT_CX),.cfg_out_cy(VEC_OUT_CY),.cfg_src_cx(VEC_SRC_CX),.cfg_src_cy(VEC_SRC_CY),
        .cfg_src_fx(VEC_SRC_FX),.cfg_src_fy(VEC_SRC_FY),.cfg_inv_fx(VEC_INV_FX),.cfg_inv_fy(VEC_INV_FY),
        .cfg_k1(VEC_K1),.cfg_k2(VEC_K2),.cfg_k3(VEC_K3),.cfg_p1(VEC_P1),.cfg_p2(VEC_P2),
        .araddr(eng_araddr),.arlen(eng_arlen),.arvalid(eng_arvalid),.arready(eng_arready),
        .rdata(eng_rdata),.rvalid(eng_rvalid),.rlast(eng_rlast),.rid(eng_rid),
        .awaddr(awaddr),.awlen(awlen),.awvalid(awvalid),.awready(awready),
        .wdata(wdata),.wstrb(wstrb),.wready(wready),.wlast(wlast),
        .processing(processing),.pending(pending),.display_active(display_active),.write_bank(write_bank),.front_bank(front_bank),
        .completed_frames(processed),.last_cycles(last_cycles),.hits(hits),.misses(misses),.queries(queries),.failed(bank_failed),.fault(bank_fault));
    wire [27:0] scan_araddr,araddr;wire [3:0] scan_arlen,arlen;
    wire scan_arvalid,scan_arready,scan_rvalid,scan_rlast,arvalid;wire [255:0] scan_rdata;
    wire [3:0] scan_rid;reg arready=0,rvalid=0,rlast=0;reg [255:0] rdata=0;
    wire bus_failed,bus_busy;wire [7:0] bus_fault;wire [31:0] scan_bursts,engine_bursts;
    wire [9:0] fifo_used,fifo_available;
    ddr_read_arbiter read_bus(.clk(clk),.rst_n(rst_n),.display_urgent(fifo_used<64),
        .c0_araddr(scan_araddr),.c1_araddr(eng_araddr),.c0_arlen(scan_arlen),.c1_arlen(eng_arlen),
        .c0_arvalid(scan_arvalid),.c1_arvalid(eng_arvalid),.c0_arready(scan_arready),.c1_arready(eng_arready),
        .c0_rdata(scan_rdata),.c1_rdata(eng_rdata),.c0_rvalid(scan_rvalid),.c1_rvalid(eng_rvalid),
        .c0_rlast(scan_rlast),.c1_rlast(eng_rlast),.c0_rid(scan_rid),.c1_rid(eng_rid),
        .araddr(araddr),.arlen(arlen),.arvalid(arvalid),.arready(arready),.rdata(rdata),.rvalid(rvalid),.rlast(rlast),.rid(4'd0),
        .failed(bus_failed),.fault(bus_fault),.busy(bus_busy),.bursts0(scan_bursts),.bursts1(engine_bursts));
    reg reader_start=0;reg [27:0] reader_base=0;reg [31:0] reader_expected=0;
    wire reader_idle,reader_done,reader_failed;wire [7:0] reader_fault;
    wire [31:0] read_beats,reader_crc,reader_frames;wire fifo_wr,fifo_wr_ready,fifo_full,fifo_rd,fifo_rd_ready,fifo_valid,fifo_empty;
    wire [255:0] fifo_wdata,fifo_rdata;
    ddr_video_reader #(.FRAME_BEATS(FB)) reader(.clk(clk),.rst_n(rst_n),.start(reader_start),
        .base_address(reader_base),.expected_checksum(reader_expected),.fifo_used(fifo_used),.fifo_ready(fifo_wr_ready),
        .fifo_wr_en(fifo_wr),.fifo_data(fifo_wdata),.araddr(scan_araddr),.arlen(scan_arlen),.arvalid(scan_arvalid),.arready(scan_arready),
        .rdata(scan_rdata),.rvalid(scan_rvalid),.rlast(scan_rlast),.rid(scan_rid),.idle(reader_idle),.done(reader_done),
        .failed(reader_failed),.fault(reader_fault),.read_beats(read_beats),.last_checksum(reader_crc),.completed_frames(reader_frames));
    video_async_fifo fifo(.wr_clk(clk),.rd_clk(pclk),.rst_n(rst_n),.wr_en(fifo_wr),.wr_data(fifo_wdata),
        .wr_full(fifo_full),.wr_ready(fifo_wr_ready),.rd_en(fifo_rd),.rd_data(fifo_rdata),.rd_valid(fifo_valid),
        .rd_empty(fifo_empty),.rd_ready(fifo_rd_ready),.rd_available(fifo_available),.wr_used(fifo_used));
    wire request_toggle,grant_ack,done_toggle,done_good,done_bank,frame_active,pix_start,pix_last,pix_valid,pix_bank;
    wire [31:0] request_epoch,done_epoch,done_id,done_crc,consumed,pix_id,scan_frames,underflows,mismatches;
    reg scan_enable=0,grant_toggle=0,grant_valid=0,grant_bank=0,done_ack=0;
    reg [31:0] grant_epoch=0,grant_id=0,grant_crc=0;
    wire hs,vs,de,display_valid,pixel_failed,draining;wire [7:0] rr,gg,bb,pixel_fault;
    ddr_video_output_1080_board #(.WIDTH(W),.HEIGHT(H),.HT(HT),.VT(VT),.HS(HS),.VS(VS),.X0(X0),.Y0(Y0),.AW(OW),.AH(OH)) scan(
        .clk(pclk),.rst_n(rst_n),.enable(scan_enable),.abort(1'b0),.abort_fault(8'd0),
        .request_toggle(request_toggle),.request_epoch(request_epoch),.grant_toggle(grant_toggle),.grant_valid(grant_valid),
        .grant_epoch(grant_epoch),.grant_checksum(grant_crc),.grant_id(grant_id),.grant_bank(grant_bank),.grant_ack_toggle(grant_ack),.done_ack_toggle(done_ack),
        .fifo_ready(fifo_rd_ready),.fifo_valid(fifo_valid),.fifo_data(fifo_rdata),.fifo_rd_en(fifo_rd),
        .hs(hs),.vs(vs),.de(de),.r(rr),.g(gg),.b(bb),.display_valid(display_valid),
        .done_toggle(done_toggle),.done_good(done_good),.done_epoch(done_epoch),.done_id(done_id),.done_crc(done_crc),.done_bank(done_bank),
        .consumed_pixels(consumed),.frame_active(frame_active),.active_id(pix_id),.active_bank(pix_bank),
        .frame_start(pix_start),.frame_last(pix_last),.pixel_valid(pix_valid),.failed(pixel_failed),.fault(pixel_fault),
        .draining(draining),.completed_frames(scan_frames),.underflows(underflows),.mismatches(mismatches));
    reg [255:0] source_words[0:FRAMES*FB-1],memory[0:4*FB-1];
    reg [48:0] expected_coordinates[0:N-1];reg [15:0] golden[0:FRAMES*N-1];
    reg [31:0] source_crcs[0:FRAMES-1],expected_crcs[0:FRAMES-1];
    integer source_epoch[0:1],result_epoch[0:1],source_release_count=0,source_reuses=0,result_reuses=0;
    integer coordinates[1:FRAMES],written[1:FRAMES],start_cycle[1:FRAMES],process_cycle[1:FRAMES],scanned[1:FRAMES];
    integer ticks=0,rleft=0,rindex=0,rbank=0,wleft=0,windex=0,wbank=0;
    integer active_id=0,active_source=0,active_result=0,total_coordinates=0,total_written=0,total_readback=0;
    integer aw_stalls=0,w_stalls=0,ar_stalls=0,peak_fifo=0,concurrent_cycles=0,ar_contention=0;
    reg held_aw=0,held_ar=0,held_w=0;reg [27:0] saved_aw=0,saved_ar=0;reg [3:0] saved_arlen=0;reg [255:0] saved_w=0;
    integer i,j,f,bank,rows,pixels_file,summary;
    reg [31:0] source_crc;reg [255:0] expected_word;
    function automatic [31:0] crc_byte(input [31:0] old,input [7:0] b);
        reg [31:0] c;integer bitno;begin c=old^b;for(bitno=0;bitno<8;bitno=bitno+1)c=c[0] ? (c>>1)^32'hedb88320:c>>1;crc_byte=c;end
    endfunction
    function automatic [23:0] expand565(input [15:0] p);
        expand565={p[15:11],p[15:13],p[10:5],p[10:9],p[4:0],p[4:2]};
    endfunction
    always @(negedge clk)begin
        ticks=ticks+1;if(ticks>24000000)$fatal(1,"bounded 720p output replay exceeded 24M core cycles");
        if(rst_n&&ticks%1000000==0)$display("OUTPUT720_PROGRESS tick=%0d processed=%0d scanned=%0d fifo=%0d",ticks,processed,scan_frames,fifo_used);
        arready=rst_n&&rleft==0&&ticks%7>=2;
        rvalid=rst_n&&rleft>0&&ticks%5!=0;rlast=rleft==1;
        if(rvalid)rdata=memory[rbank*FB+rindex];
        awready=rst_n&&wleft==0&&ticks%9>=3;
        wready=rst_n&&wleft>0&&ticks%6!=0;wlast=wleft==1;
    end
    always @(posedge clk)if(rst_n)begin
        if(source_valid&&source_ready)begin
            if(source_id<1||source_id>FRAMES||source_epoch[source_bank]!=source_id||processing)
                $fatal(1,"invalid completed source publication");
            active_id=source_id;active_source=source_bank;active_result=write_bank;
            if(result_epoch[active_result]>0)result_reuses=result_reuses+1;
            if(display_active&&active_result==front_bank)$fatal(1,"result bank reused during display lease");
            result_epoch[active_result]=source_id;start_cycle[source_id]=ticks;
        end
        if(processing&&display_active)concurrent_cycles=concurrent_cycles+1;
        if(eng_arvalid&&scan_arvalid)ar_contention=ar_contention+1;
        if(bank_core.engine.core.mapped_valid && bank_core.engine.core.mapped_ready)begin
            if(active_id<1||coordinates[active_id]>=N||bank_core.engine.core.mapped_tag!==coordinates[active_id][23:0]||
               {bank_core.engine.core.mapped_black,bank_core.engine.core.mapped_x,bank_core.engine.core.mapped_y}!==expected_coordinates[coordinates[active_id]])
                $fatal(1,"nonlinear mapper coordinate mismatch frame=%0d index=%0d",active_id,coordinates[active_id]);
            coordinates[active_id]=coordinates[active_id]+1;total_coordinates=total_coordinates+1;
        end
        if(bank_core.engine_done)begin
            if(bank_core.engine_id!=active_id||bank_core.engine_crc!==expected_crcs[active_id-1]||
               written[active_id]!=FB||coordinates[active_id]!=N||wleft!=0)
                $fatal(1,"incomplete processed result publication");
            process_cycle[active_id]=ticks;
        end
        if(source_released)begin
            if(released_bank!=active_source||written[active_id]!=FB)$fatal(1,"source released before result completion");
            source_release_count=source_release_count+1;
        end
        if(bank_failed||reader_failed||bus_failed||pixel_failed)$fatal(1,"production fault bank=%h reader=%h bus=%h scan=%h",bank_fault,reader_fault,bus_fault,pixel_fault);
        if(held_aw&&(!awvalid||awaddr!==saved_aw))$fatal(1,"AW changed while stalled");
        if(held_ar&&(!arvalid||araddr!==saved_ar||arlen!==saved_arlen))$fatal(1,"AR changed while stalled");
        if(held_w&&wdata!==saved_w)$fatal(1,"W payload changed while stalled");
        held_aw=awvalid&&!awready;saved_aw=awaddr;held_ar=arvalid&&!arready;saved_ar=araddr;saved_arlen=arlen;
        held_w=wleft>0&&!wready;saved_w=wdata;
        if(held_aw)aw_stalls=aw_stalls+1;if(held_ar)ar_stalls=ar_stalls+1;if(held_w)w_stalls=w_stalls+1;
        if(fifo_used>peak_fifo)peak_fifo=fifo_used;
        if(arvalid&&arready)begin
            if(rleft!=0||araddr[2:0]!=0)$fatal(1,"overlapping/unaligned modeled DDR read");
            rbank=araddr/STRIDE;rindex=(araddr%STRIDE)/8;
            if(rbank>3||araddr%STRIDE>=FU||rindex+arlen>=FB)$fatal(1,"read burst outside a complete frame");
            if(rbank<2)begin
                if(arlen!=7||!processing||rbank!=active_source||source_epoch[rbank]!=active_id)
                    $fatal(1,"source read outside processing ownership");
            end else if(arlen!=15||!display_active||rbank!=front_bank+2||result_epoch[rbank-2]!=grant_id)
                $fatal(1,"display read outside published result ownership");
            rleft=arlen+1;
        end
        if(rvalid)begin
            if(rleft<=0)$fatal(1,"unsolicited modeled DDR response");
            if(rbank>=2)total_readback=total_readback+1;rleft=rleft-1;rindex=rindex+1;
        end
        if(awvalid&&awready)begin
            wbank=awaddr/STRIDE;windex=(awaddr%STRIDE)/8;
            if(!processing||wbank!=active_result+2||windex!=written[active_id]||awaddr[2:0]!=0||
               awlen!=15||windex+15>=FB||wleft!=0||display_active&&wbank==front_bank+2)
                $fatal(1,"result burst outside processing lease/order");
            wleft=16;
        end
        if(wready)begin
            if(wleft<=0||wstrb!==32'hffffffff)$fatal(1,"invalid result write/mask");
            for(j=0;j<16;j=j+1)expected_word[j*16+:16]=golden[(active_id-1)*N+windex*16+j];
            if(wdata!==expected_word)$fatal(1,"processed DDR differs from CPU golden frame=%0d beat=%0d",active_id,windex);
            memory[wbank*FB+windex]=wdata;windex=windex+1;wleft=wleft-1;written[active_id]=written[active_id]+1;total_written=total_written+1;
        end
    end
    // Same held-bundle protocol as the production system, using the production
    // bank manager public ports. No hierarchical force/ownership overrides.
    reg [1:0] request_sync=0,done_sync=0,ack_sync=0;reg request_seen=0,done_seen=0;
    reg awaiting_grant=0,lease=0,reader_finished=0,pixels_finished=0;
    integer releases=0,unique_scans=0;reg [31:0] lease_epoch=0,lease_id=0,lease_crc=0,requested_epoch=0;reg lease_bank=0;
    always @(posedge clk)begin
        if(!rst_n)begin request_sync<=0;done_sync<=0;ack_sync<=0;end
        else begin
            request_sync<={request_sync[0],request_toggle};done_sync<={done_sync[0],done_toggle};ack_sync<={ack_sync[0],grant_ack};
            reader_start<=0;display_grant_ready<=0;display_done<=0;
            if(request_sync[1]!=request_seen)begin
                request_seen<=request_sync[1];requested_epoch<=request_epoch;
                if(lease||awaiting_grant||display_request||grant_toggle!=ack_sync[1])$fatal(1,"new scan before prior lease/held grant drained");
                if(display_ready&&reader_idle&&fifo_used==0)display_request<=1;
                else begin grant_epoch<=request_epoch;grant_toggle<=!grant_toggle;grant_valid<=0;end
            end
            if(display_request&&display_ready)begin display_request<=0;awaiting_grant<=1;end
            if(awaiting_grant&&display_grant_valid)begin
                if(!reader_idle||fifo_used!=0||fifo_available!=0||display_id<1||display_id>FRAMES||written[display_id]!=FB)
                    $fatal(1,"grant before complete result or prior reader/FIFO drain");
                display_grant_ready<=1;awaiting_grant<=0;
                lease<=1;lease_epoch<=requested_epoch;lease_id<=display_id;lease_bank<=display_base/STRIDE-2;lease_crc<=display_crc;
                reader_finished<=0;pixels_finished<=0;reader_base<=display_base;reader_expected<=display_crc;reader_start<=1;
                grant_epoch<=requested_epoch;grant_id<=display_id;grant_crc<=display_crc;grant_bank<=display_base/STRIDE-2;grant_valid<=1;grant_toggle<=!grant_toggle;
            end
            if(reader_done)begin
                if(!lease||reader_crc!==expected_crcs[lease_id-1]||read_beats!=FB)$fatal(1,"reader CRC/count differs from current lease");
                reader_finished<=1;
            end
            if(done_sync[1]!=done_seen)begin
                done_seen<=done_sync[1];
                if(!lease||!done_good||done_id!=lease_id||done_bank!=lease_bank||done_epoch!=lease_epoch||done_crc!==lease_crc||consumed!=N)
                    $fatal(1,"pixel completion ID/bank/epoch/CRC/count differs");
                pixels_finished<=1;
            end
            if(lease&&reader_finished&&pixels_finished&&reader_idle&&fifo_used==0&&fifo_available==0&&!fifo_valid)begin
                if(scan.frame_active||scan.queued!=0||scan.inflight!=0||rleft>0&&rbank>=2)$fatal(1,"result release before actual scan/transaction drain");
                lease<=0;releases<=releases+1;done_ack<=done_sync[1];display_done<=1;display_done_bank<=lease_bank;
                if(scanned[lease_id]==0)begin scanned[lease_id]=1;unique_scans<=unique_scans+1;end
                $fdisplay(rows,"%0d,%0d,%0d,%0d,%0d,%0d,%0d,%08x,%08x,%08x,%08x,%0d",lease_id,lease_bank,N,FB,start_cycle[lease_id],process_cycle[lease_id],ticks,source_crcs[lease_id-1],lease_crc,reader_crc,done_crc,lease_epoch);$fflush(rows);
                $display("OUTPUT720_FRAME_PASS id=%0d result_bank=%0d crc=%08x release_cycle=%0d",lease_id,lease_bank,lease_crc,ticks);
            end
        end
    end
    integer output_tick=0,origin_tick=0,out_x=0,out_y=0,scan_count=0,scan_start_tick=0,total_pixels=0;
    integer border_pixels=0,de_pixels=0,complete_rasters=0,current_scan=0;
    reg raster_seen=0,previous_vs=0;reg [31:0] pixel_crc=32'hffffffff;reg [15:0] observed;
    always @(posedge pclk)if(rst_n)begin
        #1;output_tick=output_tick+1;
        if(vs&&!previous_vs)begin
            if(raster_seen)begin
                if(output_tick-origin_tick!=HT*VT||de_pixels!=OW*OH)$fatal(1,"full HDMI raster period/DE area differs");
                complete_rasters=complete_rasters+1;
            end
            origin_tick=output_tick;raster_seen=1;de_pixels=0;
        end
        previous_vs=vs;
        if(raster_seen)begin
            out_x=(output_tick-origin_tick)%HT;out_y=((output_tick-origin_tick)/HT)%VT;
            if(hs!==(out_x<HS)||vs!==(out_y<VS)||de!==(out_x>=X0&&out_x<X0+OW&&out_y>=Y0&&out_y<Y0+OH))
                $fatal(1,"registered HDMI HS/VS/DE differs");
            if(de)begin
                de_pixels=de_pixels+1;
                if(out_x<WX||out_x>=WX+W||out_y<WY||out_y>=WY+H)begin
                    if({rr,gg,bb}!==0||pix_valid)$fatal(1,"centered native 720p border not black");
                    border_pixels=border_pixels+1;
                end
            end
        end
        if(pix_valid)begin
            if(!de||!lease||pix_id!=lease_id||pix_bank!=lease_bank)$fatal(1,"output pixel outside current granted epoch");
            if(pix_start)begin
                if(out_x!=WX||out_y!=WY)$fatal(1,"scan did not begin at native centered 720p origin");
                current_scan=pix_id;scan_count=0;pixel_crc=32'hffffffff;scan_start_tick=output_tick;
            end
            if(scan_count>=N||output_tick-scan_start_tick!=(scan_count/W)*HT+scan_count%W)$fatal(1,"native 720p pixel cadence/count differs");
            if({rr,gg,bb}!==expand565(golden[(current_scan-1)*N+scan_count]))$fatal(1,"actual DE/RGB mismatch frame=%0d pixel=%0d",current_scan,scan_count);
            observed={rr[7:3],gg[7:2],bb[7:3]};$fdisplay(pixels_file,"%0d %04x",current_scan,observed);
            pixel_crc=crc_byte(crc_byte(pixel_crc,observed[7:0]),observed[15:8]);scan_count=scan_count+1;total_pixels=total_pixels+1;
            if(pix_last&&(scan_count!=N||~pixel_crc!==expected_crcs[current_scan-1]))$fatal(1,"last scanned pixel/CPU CRC differs");
        end else if({rr,gg,bb}!==0)$fatal(1,"inactive raster not black");
    end
    initial begin
        if(VEC_WIDTH!=W||VEC_HEIGHT!=H)$fatal(1,"native 720p fixture geometry required");
        for(i=0;i<2;i=i+1)begin source_epoch[i]=0;result_epoch[i]=0;end
        for(i=1;i<=FRAMES;i=i+1)begin coordinates[i]=0;written[i]=0;start_cycle[i]=0;process_cycle[i]=0;scanned[i]=0;end
        $readmemh("coordinates.mem",expected_coordinates);
        $readmemh("source0.mem",source_words,0,FB-1);$readmemh("source1.mem",source_words,FB,2*FB-1);$readmemh("source2.mem",source_words,2*FB,3*FB-1);
        $readmemh("expected0.mem",golden,0,N-1);$readmemh("expected1.mem",golden,N,2*N-1);$readmemh("expected2.mem",golden,2*N,3*N-1);
        $readmemh("source-crcs.mem",source_crcs);$readmemh("expected-crcs.mem",expected_crcs);
        rows=$fopen("frames.csv","w");pixels_file=$fopen("scan-pixels.mem","w");
        $fdisplay(rows,"frame_id,result_bank,pixels,result_beats,start_cycle,process_done_cycle,release_cycle,source_crc32,result_crc32,reader_crc32,scan_crc32,request_epoch");
        repeat(12)@(negedge clk);rst_n=1;repeat(12)@(negedge clk);scan_enable=1;
        for(f=0;f<FRAMES;f=f+1)begin
            bank=f%2;wait(source_writable[bank]);@(negedge clk);
            if(source_epoch[bank]>0)source_reuses=source_reuses+1;source_epoch[bank]=f+1;
            source_crc=32'hffffffff;
            for(i=0;i<FB;i=i+1)begin
                memory[bank*FB+i]=source_words[f*FB+i];
                for(j=0;j<32;j=j+1)source_crc=crc_byte(source_crc,source_words[f*FB+i][j*8+:8]);
            end
            if(~source_crc!==source_crcs[f])$fatal(1,"preloaded synthetic source CRC differs");
            source_id=f+1;source_bank=bank;source_valid=1;
            @(posedge clk);while(!source_ready)@(posedge clk);
            @(negedge clk);source_valid=0;
        end
        wait(unique_scans==FRAMES);@(negedge clk);scan_enable=0;repeat(40)@(negedge clk);
        if(lease||display_active||pending||processing||display_request||awaiting_grant||fifo_used!=0||fifo_available!=0||!fifo_empty||fifo_valid||
           scan.queued!=0||scan.inflight!=0||scan.done_pending||!reader_idle||bus_busy||rleft!=0||wleft!=0||underflows||mismatches)
            $fatal(1,"final source/result/read/FIFO/raster ownership did not drain");
        if(processed!=FRAMES||source_release_count!=FRAMES||total_coordinates!=FRAMES*N||total_written!=FRAMES*FB||
           total_pixels!=scan_frames*N||total_readback!=scan_frames*FB||reader_frames!=scan_frames||releases!=scan_frames||
           source_reuses<1||result_reuses<1||aw_stalls==0||w_stalls==0||ar_stalls==0||peak_fifo==0||
           concurrent_cycles==0||ar_contention==0||complete_rasters<3||border_pixels==0)
            $fatal(1,"full 720p scan/drain/ownership/concurrency coverage differs");
        $fclose(pixels_file);$fclose(rows);summary=$fopen("summary.json","w");
        $fdisplay(summary,"{\"passed\":true,\"frames_processed\":%0d,\"frames_unique_scanned\":%0d,\"scan_frames\":%0d,\"coordinates_compared\":%0d,\"pixels_compared\":%0d,\"source_bank_reuses\":%0d,\"result_bank_reuses\":%0d,\"bank_releases\":%0d,\"result_beats\":%0d,\"display_read_beats\":%0d,\"underflows\":%0d,\"crc_mismatches\":%0d,\"aw_stall_cycles\":%0d,\"w_stall_cycles\":%0d,\"ar_stall_cycles\":%0d,\"fifo_peak\":%0d,\"concurrent_process_display_cycles\":%0d,\"read_contention_cycles\":%0d,\"complete_hdmi_rasters\":%0d,\"border_pixels_checked\":%0d,\"final_drain\":true}",processed,unique_scans,scan_frames,total_coordinates,total_pixels,source_reuses,result_reuses,releases,total_written,total_readback,underflows,mismatches,aw_stalls,w_stalls,ar_stalls,peak_fifo,concurrent_cycles,ar_contention,complete_rasters,border_pixels);$fclose(summary);
        $display("PASS camera720 output: full 1280x720 nonlinear coordinates and RGB565, production four-bank ownership, 1080p30 native centered scan, concurrent processing/display, DDR backpressure, CRC and final drain");$finish;
    end
endmodule
