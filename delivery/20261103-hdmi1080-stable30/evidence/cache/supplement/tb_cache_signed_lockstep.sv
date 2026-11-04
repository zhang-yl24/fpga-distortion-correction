`timescale 1ns/1ps
// Adapted from distortion/tests/tb_scatter4_neighbour_cache.sv for the
// exact frozen HDMI cache and the packed candidate. Both use the same golden.
// Data is computed independently from linear pixel number, bank and frame epoch.
module tb_cache_directed;
    localparam WIDTH=256,HEIGHT=128,INDEX_BITS=7,LINES=1<<INDEX_BITS;
    `ifdef PACKED32
    localparam PACKED32=1;
`else
    localparam PACKED32=0;
`endif
    localparam ADDRESS_BITS=INDEX_BITS+(PACKED32 ? 5:6),STRIDE=262144;
    localparam GROUPS=PACKED32 ? 16:32, LAST_GROUP=GROUPS-1;
    localparam WORD_BITS=PACKED32 ? 32:16;
    localparam CONFLICT_Y=(LINES*128)/WIDTH;
    reg clk=0;always #4 clk=~clk;
    reg rst_n=0,frame_valid=0,in_valid=0;
    reg [27:0] frame_base=0;
    reg signed [23:0] in_x=0,in_y=0;
    reg [24:0] in_tag=0;
    wire frame_ready,in_ready,out_valid,failed;
    wire [23:0] p00,p10,p01,p11;
    wire [7:0] fx,fy,fault;wire [24:0] out_tag;
    wire [27:0] araddr;wire [3:0] arlen;wire arvalid;
    reg arready=0,rvalid=0,rlast=0,out_ready=0;
    reg [255:0] rdata=0;reg [3:0] rid=0;
    wire [31:0] hits,misses,completed_queries;
    ddr_neighbour_cache_scatter4_tag_prefetch_local #(.WIDTH(WIDTH),.HEIGHT(HEIGHT),.TAG_W(25),
        .INDEX_BITS(INDEX_BITS),.TIMEOUT_BITS(10)) dut(
        .clk(clk),.rst_n(rst_n),.frame_valid(frame_valid),.frame_ready(frame_ready),.frame_base(frame_base),
        .in_valid(in_valid),.in_ready(in_ready),.in_x(in_x),.in_y(in_y),.in_tag(in_tag),
        .out_valid(out_valid),.out_ready(out_ready),.p00(p00),.p10(p10),.p01(p01),.p11(p11),
        .fx(fx),.fy(fy),.out_tag(out_tag),.araddr(araddr),.arlen(arlen),.arvalid(arvalid),.arready(arready),
        .rdata(rdata),.rvalid(rvalid),.rlast(rlast),.rid(rid),.failed(failed),.fault(fault),
        .hits(hits),.misses(misses),.completed_queries(completed_queries));

    integer ticks=0,left=0,beat=0,burst_pixel=0,burst_bank=0,burst_epoch=0;
    integer served_beats=0,bursts=0,active_bank=0,active_epoch=0,accepted_frames=0;
    integer sent=0,received=0,mode=0;
    reg checking=1,force_ar_stall=0,force_output_stall=0;
    reg [136:0] expected[0:255];
    reg out_held=0,ar_held=0;
    reg [136:0] held_output;
    reg [31:0] held_ar;

    // Coverage counters are deliberately NOT reset by individual DUT resets.
    integer cov_ar_stall=0,cov_r_gap=0,cov_out_stall=0,cov_input_stall=0;
    integer cov_fifo_full=0,cov_pending_queue=0,cov_read=0,cov_scatter=0;
    integer cov_first_quad=0,cov_last_quad=0,cov_published=0,cov_ram_verified=0;
    integer cov_replacement=0,cov_same_bank=0,cov_last_reset=0,cov_reset_refill=0;
    integer cov_tag_high=0,cov_tag_low=0,cov_normal_outputs=0;
    integer cov_bad_rid=0,cov_early_last=0,cov_missing_last=0,cov_unsolicited=0,cov_queued_fault=0;
    integer cov_slow_empty=0,cov_lower_read=0;
    integer cov_last_frame_request=0,cov_last_frame_pending=0,cov_last_frame_out_stall=0,cov_last_frame_refill=0;

    function automatic [15:0] word565(input integer pos,input integer bank,input integer epoch);
        word565=(pos*73+16'h05a3+(pos>>7)*337+(pos^(pos>>4))*11+
                 bank*16'h3333+epoch*16'h0249)&16'hffff;
    endfunction
    function automatic [23:0] expected_rgb(input integer x,input integer y,input integer bank,input integer epoch);
        reg [15:0] p;
        begin
            if(x<0 || x>=WIDTH || y<0 || y>=HEIGHT)expected_rgb=0;
            else begin
                p=word565(y*WIDTH+x,bank,epoch);
                expected_rgb={p[15:11],p[15:13],p[10:5],p[10:9],p[4:0],p[4:2]};
            end
        end
    endfunction

    // No zero-latency DDR shortcut: each reserved 8-beat burst has real gaps.
    always @(negedge clk)begin
        arready=rst_n && !force_ar_stall && left==0 && ticks%7>=2;
        rvalid=rst_n && left>0 && ticks%5!=0;
        rlast=left==1;
        rid=(mode==1 && beat==3) ? 4'h9:4'h0;
        if(mode==2 && beat==3)rlast=1;
        if(mode==3 && left==1)rlast=0;
        if(mode==4 && left==0 && rst_n)begin rvalid=1;rlast=1;end
        for(integer lane=0;lane<16;lane=lane+1)
            rdata[lane*16+:16]=word565(burst_pixel+beat*16+lane,burst_bank,burst_epoch);
        out_ready=rst_n && !force_output_stall && ticks%11>=3;
    end

    // Sample after an earlier RAM-writing edge. This is intentionally not a
    // comparison against fill_buffer or another cache implementation.
    reg previous_scatter=0,previous_last=0,previous_frame=0,valid_history=0;
    reg [ADDRESS_BITS-1:0] previous_a,previous_b;
    reg [INDEX_BITS-1:0] previous_line;
    reg [24:0] previous_block,previous_old_tag;
    reg [WORD_BITS-1:0] previous_even_a,previous_odd_a,previous_even_b,previous_odd_b;
    reg [LINES-1:0] previous_valid_lines;
    integer groups_in_fill=0;

    always @(posedge clk)begin
        ticks<=ticks+1;
        if(!rst_n)begin
            left<=0;beat<=0;served_beats<=0;bursts<=0;
            sent<=0;received<=0;active_bank<=0;active_epoch<=0;accepted_frames<=0;
            out_held<=0;ar_held<=0;previous_scatter<=0;previous_last<=0;
            previous_frame<=0;valid_history<=0;
        end else begin
            if(ar_held && (!arvalid || {araddr,arlen}!==held_ar))$fatal(1,"SCATTER4 AR changed while stalled");
            ar_held<=arvalid&&!arready;held_ar<={araddr,arlen};
            if(arvalid&&!arready)cov_ar_stall=cov_ar_stall+1;
            if(left>0&&!rvalid)cov_r_gap=cov_r_gap+1;
            if(in_valid&&!in_ready)cov_input_stall=cov_input_stall+1;
            if(dut.queue_count==2)cov_fifo_full=cov_fifo_full+1;
            if(frame_valid && dut.queue_count!=0)cov_pending_queue=cov_pending_queue+1;
            if(dut.queue_count>2 || (frame_ready && dut.queue_count!=0))$fatal(1,"SCATTER4 FIFO/frame ownership differs");
            if(frame_valid && in_ready)$fatal(1,"SCATTER4 pending frame admitted new input");
            if(dut.inner.accept_slow)begin
                if(dut.inner.empty!==1'b1 || dut.inner.v0!==1'b0 || dut.inner.v1!==1'b0)
                    $fatal(1,"SCATTER4 slow query started before the fast pipeline drained");
                cov_slow_empty=cov_slow_empty+1;
            end

            if(frame_valid&&frame_ready)begin
                if(sent!=received || left!=0 || out_valid || dut.queue_count!=0)
                    $fatal(1,"SCATTER4 new frame accepted before queued/results/DDR drain");
                active_bank<=frame_base==STRIDE;active_epoch<=active_epoch+1;
                accepted_frames<=accepted_frames+1;
            end
            if(checking)begin
                if(failed)$fatal(1,"Unexpected SCATTER4 fault %h",fault);
                if(out_held && (!out_valid || {p00,p10,p01,p11,fx,fy,out_tag}!==held_output))
                    $fatal(1,"SCATTER4 output/fractions/TAG25 changed under backpressure");
                if(in_valid&&in_ready)begin
                    if(sent>=256)$fatal(1,"SCATTER4 scoreboard bound exceeded");
                    expected[sent]<={expected_rgb($signed(in_x)>>>8,$signed(in_y)>>>8,active_bank,active_epoch),
                        expected_rgb(($signed(in_x)>>>8)+1,$signed(in_y)>>>8,active_bank,active_epoch),
                        expected_rgb($signed(in_x)>>>8,($signed(in_y)>>>8)+1,active_bank,active_epoch),
                        expected_rgb(($signed(in_x)>>>8)+1,($signed(in_y)>>>8)+1,active_bank,active_epoch),
                        in_x[7:0],in_y[7:0],in_tag};
                    sent<=sent+1;
                end
                if(out_valid&&!out_ready)cov_out_stall=cov_out_stall+1;
                if(out_valid&&out_ready)begin
                    if(received>=sent || {p00,p10,p01,p11,fx,fy,out_tag}!==expected[received])
                        $fatal(1,"SCATTER4 independent four-neighbour oracle mismatch query%0d",received);
                    if(out_tag[24])cov_tag_high=cov_tag_high+1;else cov_tag_low=cov_tag_low+1;
                    received<=received+1;cov_normal_outputs=cov_normal_outputs+1;
                end
            end
            out_held<=checking&&out_valid&&!out_ready;held_output<={p00,p10,p01,p11,fx,fy,out_tag};

            if(arvalid&&arready)begin
                if(left!=0 || arlen!=7 || araddr[5:0]!=0 ||
                   (araddr>=STRIDE ? araddr-STRIDE:araddr)*2+127>=WIDTH*HEIGHT)
                    $fatal(1,"SCATTER4 DDR 8-beat/128-pixel reservation outside frame");
                burst_bank<=araddr>=STRIDE;
                if((araddr>=STRIDE)!=active_bank)$fatal(1,"SCATTER4 used changing/unaccepted frame base");
                burst_pixel<=(araddr>=STRIDE ? araddr-STRIDE:araddr)*2;
                burst_epoch<=active_epoch;left<=8;beat<=0;served_beats<=0;bursts<=bursts+1;
            end
            if(rvalid&&left>0)begin left<=left-1;beat<=beat+1;served_beats<=served_beats+1;end

            if(previous_scatter)begin
                if(dut.inner.even_pixels[previous_a]!==previous_even_a ||
                   dut.inner.odd_pixels[previous_a]!==previous_odd_a ||
                   dut.inner.even_pixels[previous_b]!==previous_even_b ||
                   dut.inner.odd_pixels[previous_b]!==previous_odd_b)
                    $fatal(1,"SCATTER4 parity/address/lane write differs from independent DDR source formula");
                cov_ram_verified=cov_ram_verified+1;
                if(previous_last)begin
                    if(dut.inner.valid_lines[previous_line]!==1'b1 || dut.inner.tags[previous_line]!==previous_block)
                        $fatal(1,"SCATTER4 last packed writes did not publish valid/tag on the next observation edge");
                    cov_published=cov_published+1;
                end else begin
                    if(dut.inner.valid_lines[previous_line]!==1'b0 || dut.inner.tags[previous_line]!==previous_old_tag)
                        $fatal(1,"SCATTER4 valid/tag published before all128 pixels were written");
                end
            end
            if(previous_frame && dut.inner.valid_lines!=={LINES{1'b0}})
                $fatal(1,"SCATTER4 same-bank frame did not invalidate all lines");
            if(valid_history && !previous_frame &&
               (dut.inner.valid_lines & ~previous_valid_lines)!={LINES{1'b0}} && !previous_last)
                $fatal(1,"SCATTER4 line became valid without a completed final scatter group");
            previous_valid_lines<=dut.inner.valid_lines;valid_history<=1;
            previous_frame<=frame_valid&&frame_ready;
            previous_scatter<=dut.inner.scatter_write;
            previous_last<=dut.inner.scatter_write&&dut.inner.scatter_group==LAST_GROUP;
            if(dut.inner.read_enable)cov_read=cov_read+1;
            if(dut.inner.read_lower)cov_lower_read=cov_lower_read+1;
            if(dut.inner.scatter_write)begin
                cov_scatter=cov_scatter+1;
                if(dut.inner.read_enable || dut.inner.read_lower || served_beats!=8 || dut.inner.fill_beat!=7)
                    $fatal(1,"SCATTER4 read/write overlap or scatter before all8 DDR beats");
                if(dut.inner.write_address_a===dut.inner.write_address_b)
                    $fatal(1,"SCATTER4 two writes collide on a port address of either parity RAM");
                if(dut.inner.write_address_a!=={dut.inner.selected_line,dut.inner.scatter_group,1'b0} ||
                   dut.inner.write_address_b!=={dut.inner.selected_line,dut.inner.scatter_group,1'b1})
                    $fatal(1,"SCATTER4 two-address group mapping differs");
                if(dut.inner.valid_lines[dut.inner.selected_line]!==1'b0)
                    $fatal(1,"SCATTER4 line exposed valid before final writing edge");
                if(dut.inner.scatter_group==0)begin groups_in_fill=0;cov_first_quad=cov_first_quad+1;end
                if(dut.inner.scatter_group!=groups_in_fill)$fatal(1,"SCATTER4 groups skipped/repeated");
                groups_in_fill=groups_in_fill+1;
                if(dut.inner.scatter_group==LAST_GROUP)begin
                    if(groups_in_fill!=GROUPS)$fatal(1,"SCATTER4 line scatter group count differs");
                    cov_last_quad=cov_last_quad+1;
                end
                previous_a<=dut.inner.write_address_a;previous_b<=dut.inner.write_address_b;
                previous_line<=dut.inner.selected_line;previous_block<=dut.inner.selected_block;
                previous_old_tag<=dut.inner.tags[dut.inner.selected_line];
                if(PACKED32)begin
                    previous_even_a<={word565(burst_pixel+8*dut.inner.scatter_group+2,burst_bank,burst_epoch),word565(burst_pixel+8*dut.inner.scatter_group,burst_bank,burst_epoch)};
                    previous_odd_a<={word565(burst_pixel+8*dut.inner.scatter_group+3,burst_bank,burst_epoch),word565(burst_pixel+8*dut.inner.scatter_group+1,burst_bank,burst_epoch)};
                    previous_even_b<={word565(burst_pixel+8*dut.inner.scatter_group+6,burst_bank,burst_epoch),word565(burst_pixel+8*dut.inner.scatter_group+4,burst_bank,burst_epoch)};
                    previous_odd_b<={word565(burst_pixel+8*dut.inner.scatter_group+7,burst_bank,burst_epoch),word565(burst_pixel+8*dut.inner.scatter_group+5,burst_bank,burst_epoch)};
                end else begin
                previous_even_a<=word565(burst_pixel+4*dut.inner.scatter_group,burst_bank,burst_epoch);
                previous_odd_a<=word565(burst_pixel+4*dut.inner.scatter_group+1,burst_bank,burst_epoch);
                previous_even_b<=word565(burst_pixel+4*dut.inner.scatter_group+2,burst_bank,burst_epoch);
                previous_odd_b<=word565(burst_pixel+4*dut.inner.scatter_group+3,burst_bank,burst_epoch);
                end
            end
        end
    end

    task automatic reset_all;
        begin
            @(negedge clk);rst_n=0;frame_valid=0;in_valid=0;mode=0;
            force_ar_stall=0;force_output_stall=0;
            repeat(6)@(negedge clk);rst_n=1;repeat(2)@(negedge clk);
            if(dut.inner.valid_lines!=={LINES{1'b0}} || out_valid || dut.queue_count!=0)
                $fatal(1,"SCATTER4 reset resurrected line/output/FIFO state");
        end
    endtask
    task automatic select_frame(input [27:0] address);
        begin
            @(negedge clk);frame_base=address;frame_valid=1;
            do @(posedge clk);while(!frame_ready);
            @(negedge clk);frame_valid=0;
        end
    endtask
    task automatic query(input integer x,input integer y,input [24:0] tag);
        begin
            @(negedge clk);in_x=x;in_y=y;in_tag=tag;in_valid=1;
            do @(posedge clk);while(!in_ready);
            @(negedge clk);in_valid=0;in_x=24'sh7fff01;in_y=-24'sd257;in_tag=0;
            if(!frame_valid)frame_base=28'h1234500;
        end
    endtask
    task automatic drain;
        integer limit;
        begin
            limit=0;
            while(received!=sent && limit<10000)begin @(negedge clk);limit=limit+1;end
            @(negedge clk);
            if(received!=sent || completed_queries!=received || left!=0)
                $fatal(1,"SCATTER4 query/result/DDR drain did not complete");
        end
    endtask
    task automatic fault_case(input integer kind,input [7:0] expected_fault);
        begin
            checking=0;reset_all();select_frame(0);mode=kind;
            if(kind!=4)begin
                force_ar_stall=1;
                query(127*256+37,0,25'h1000800+kind);wait(arvalid);
                query(17*256+3,0,25'h1000810+kind);
                query(18*256+5,0,25'h0000820+kind);
                if(dut.queue_count!=2)$fatal(1,"SCATTER4 error case did not retain two queued wrapper queries");
                force_ar_stall=0;
            end
            wait(failed);repeat(4)@(negedge clk);
            if(fault!=expected_fault || in_ready || frame_ready || out_valid || dut.inner.valid_lines!=={LINES{1'b0}})
                $fatal(1,"SCATTER4 malformed/unsolicited return was not quarantined kind%0d fault%h",kind,fault);
            if(kind!=4)begin
                if(dut.queue_count!=2)$fatal(1,"SCATTER4 fault consumed queued metadata");
                cov_queued_fault=cov_queued_fault+1;
            end
            repeat(12)@(negedge clk);
            if(!failed || fault!=expected_fault || out_valid)$fatal(1,"SCATTER4 fault was not sticky");
            case(kind)
                1:cov_bad_rid=cov_bad_rid+1;
                2:cov_early_last=cov_early_last+1;
                3:cov_missing_last=cov_missing_last+1;
                4:cov_unsolicited=cov_unsolicited+1;
            endcase
        end
    endtask

    integer before_bursts,before_frames;
    integer edge_x[0:7],edge_y[0:7];
    initial begin
        edge_x[0]=-8388608;edge_x[1]=-257;edge_x[2]=-1;edge_x[3]=0;
        edge_x[4]=255;edge_x[5]=(WIDTH-1)*256+255;edge_x[6]=WIDTH*256;edge_x[7]=8388607;
        edge_y[0]=-8388608;edge_y[1]=-257;edge_y[2]=-1;edge_y[3]=0;
        edge_y[4]=255;edge_y[5]=(HEIGHT-1)*256+255;edge_y[6]=HEIGHT*256;edge_y[7]=8388607;
    end
    initial begin
        checking=1;reset_all();select_frame(0);
        // Force a known AR stall, then verify all4 boundary lines including
        // each 128-pixel line's first/last, even/odd words through RAM checks.
        force_ar_stall=1;query(127*256+53,0,25'h1000001);wait(arvalid);
        repeat(7)@(negedge clk);force_ar_stall=0;drain();
        if(bursts!=4)$fatal(1,"SCATTER4 four boundary neighbour lines were not fetched");
        query(0,0,25'h0000002);drain();
        query(1*256+255,0,25'h1000003);drain();
        query((WIDTH-1)*256+201,(HEIGHT-1)*256+63,25'h0000004);drain();
        query(-1,-1,25'h1000005);drain();
        // Exhaustive cross-product of signed Q16.8 edge coordinates.
        for(integer sx=0;sx<8;sx=sx+1)begin
            for(integer sy=0;sy<8;sy=sy+1)begin
                query(edge_x[sx],edge_y[sy],25'h1000900+sx*8+sy);drain();
            end
        end
        $display("PASS SIGNED FIFO PREDECODE edge_queries=64");

        // INDEX7: row64's block128 aliases row0's block0, not a smaller cache.
        query(17*256+29,0,25'h0000011);drain();before_bursts=bursts;
        query(17*256+29,CONFLICT_Y*256+77,25'h1000012);drain();
        if(bursts<=before_bursts)$fatal(1,"SCATTER4 same-index new-tag query did not replace");
        before_bursts=bursts;query(17*256+29,77,25'h0000013);drain();
        if(bursts<=before_bursts)$fatal(1,"SCATTER4 replaced old-tag query did not refill");
        cov_replacement=cov_replacement+1;
        before_bursts=bursts;query(17*256+29,77,25'h1000014);drain();
        if(bursts!=before_bursts)$fatal(1,"SCATTER4 warm hit unexpectedly refilled");

        before_bursts=bursts;select_frame(0);query(17*256+29,77,25'h0000021);drain();
        if(bursts<=before_bursts)$fatal(1,"SCATTER4 same-bank new epoch did not invalidate");
        cov_same_bank=cov_same_bank+1;
        select_frame(STRIDE);query(127*256+23,77,25'h1000022);drain();
        for(integer x=0;x<128;x=x+1)query(x*256+(x*17)%256,17*256+(x*29)%256,25'h1000300+x);
        drain();
        $display("PASS SCATTER4 INDEX7 full128-pixel parity/first-last, direct-map tag replacement, same/new bank epochs and TAG25 oracle");

        // Fill the real wrapper FIFO, hold a fourth request under full pressure,
        // then request the next frame while old queued work/results still exist.
        reset_all();select_frame(0);force_output_stall=1;
        query(127*256+1,0,25'h1000101);
        query(2*256+2,0,25'h0000102);
        query(3*256+3,0,25'h1000103);
        wait(out_valid&&dut.queue_count==2);
        fork
            begin query(4*256+4,0,25'h0000104);end
            begin
                wait(in_valid&&!in_ready);repeat(9)@(negedge clk);
                force_output_stall=0;
            end
        join
        force_output_stall=1;frame_base=0;frame_valid=1;
        repeat(12)begin @(negedge clk);
            if(frame_ready || in_ready)$fatal(1,"SCATTER4 new frame bypassed pending queued result ownership");
        end
        force_output_stall=0;
        do @(posedge clk);while(!frame_ready);
        @(negedge clk);frame_valid=0;
        if(received!=4 || sent!=4 || dut.queue_count!=0 || completed_queries!=4)
            $fatal(1,"SCATTER4 frame_valid prevented old FIFO/query/results draining");
        query(17*256+19,43,25'h0000106);drain();
        $display("PASS SCATTER4 FIFO2 full input/output stalls, stable fractions/TAG25 and pending-frame drain");

        // Request the SAME bank immediately before its first line's final
        // scatter edge. Keep a new input offered, but forbid its admission;
        // old scatter, remaining neighbour loads and the held result must drain.
        reset_all();select_frame(0);force_output_stall=1;
        query(17*256+31,77,25'h1000181);
        wait(dut.inner.scatter_write&&dut.inner.scatter_group==LAST_GROUP);
        @(negedge clk);
        if(!dut.inner.scatter_write || dut.inner.scatter_group!=LAST_GROUP)
            $fatal(1,"SCATTER4 missed last-write pending-frame point");
        before_frames=accepted_frames;
        frame_base=0;frame_valid=1;
        in_x=23*256+11;in_y=31;in_tag=25'h0000182;in_valid=1;
        cov_last_frame_request=cov_last_frame_request+1;
        while(!out_valid)begin
            @(negedge clk);
            if(frame_ready || in_ready || accepted_frames!=before_frames)
                $fatal(1,"SCATTER4 final-scatter pending frame/input accepted before old result existed");
            cov_last_frame_pending=cov_last_frame_pending+1;
        end
        repeat(9)begin
            @(negedge clk);
            if(frame_ready || in_ready || accepted_frames!=before_frames || sent!=1 || received!=0 ||
               !out_valid || out_ready)
                $fatal(1,"SCATTER4 final-scatter pending frame bypassed its held old result");
            cov_last_frame_out_stall=cov_last_frame_out_stall+1;
        end
        force_output_stall=0;
        do begin
            @(posedge clk);
            if(in_ready)$fatal(1,"SCATTER4 pending same-bank frame admitted offered new input");
        end while(!frame_ready);
        if(sent!=1 || received!=1 || completed_queries!=1)
            $fatal(1,"SCATTER4 same-bank frame accepted before exact old-query output drain");
        @(negedge clk);frame_valid=0;in_valid=0;
        if(accepted_frames!=before_frames+1 || dut.inner.valid_lines!=={LINES{1'b0}})
            $fatal(1,"SCATTER4 final-scatter same-bank frame did not accept once and clear all metadata");
        before_bursts=bursts;
        query(17*256+31,77,25'h0000183);drain();
        if(bursts<=before_bursts)
            $fatal(1,"SCATTER4 final-scatter same-bank frame reused old-epoch pixels without refill");
        cov_last_frame_refill=cov_last_frame_refill+1;
        $display("PASS SCATTER4 frame_valid at final group: no new input, exact old-result drain, same-bank invalidate and independent new-epoch refill");

        // Reset is sampled at the last scatter writing edge. RAM contents may
        // survive reset, but no partially written line may be published/reused.
        reset_all();select_frame(0);query(17*256+31,77,25'h1000201);
        wait(dut.inner.scatter_write&&dut.inner.scatter_group==LAST_GROUP);
        @(negedge clk);
        if(!dut.inner.scatter_write || dut.inner.scatter_group!=LAST_GROUP)$fatal(1,"SCATTER4 missed last-write reset point");
        cov_last_reset=cov_last_reset+1;
        rst_n=0;frame_valid=0;in_valid=0; // Assert BEFORE the final group writing edge.
        reset_all();select_frame(0);before_bursts=bursts;
        query(17*256+31,77,25'h0000202);drain();
        if(bursts<=before_bursts)$fatal(1,"SCATTER4 partially scattered/reset RAM was reused without refilling");
        cov_reset_refill=cov_reset_refill+1;
        $display("PASS SCATTER4 reset on last final packed write edge, invalid metadata and mandatory refill");

        fault_case(1,8'h03);fault_case(2,8'h03);fault_case(3,8'h03);fault_case(4,8'h04);
        $display("PASS SCATTER4 RID/early-RLAST/missing-final-RLAST/unsolicited-R sticky wrapper quarantine");
        if(cov_ar_stall==0 || cov_r_gap==0 || cov_out_stall==0 || cov_input_stall==0 ||
           cov_fifo_full==0 || cov_pending_queue==0 || cov_read==0 || cov_scatter==0 ||
           cov_first_quad==0 || cov_last_quad==0 || cov_published==0 || cov_ram_verified==0 ||
           cov_replacement==0 || cov_same_bank==0 || cov_last_reset==0 || cov_reset_refill==0 ||
           cov_tag_high==0 || cov_tag_low==0 || cov_normal_outputs==0 ||
           cov_slow_empty==0 || cov_lower_read==0 || cov_last_frame_request==0 ||
           cov_last_frame_pending==0 || cov_last_frame_out_stall==0 || cov_last_frame_refill==0 ||
           cov_bad_rid==0 || cov_early_last==0 || cov_missing_last==0 || cov_unsolicited==0 || cov_queued_fault==0)
            $fatal(1,"SCATTER4 mandatory pressure/reset/replacement/fault coverage was vacuous");
        $display("SCATTER4 coverage arstall=%0d rgap=%0d outstall=%0d install=%0d fifo_full=%0d frame_queue=%0d scatter=%0d ramverify=%0d last=%0d publish=%0d resetlast=%0d queuedfault=%0d",
            cov_ar_stall,cov_r_gap,cov_out_stall,cov_input_stall,cov_fifo_full,cov_pending_queue,
            cov_scatter,cov_ram_verified,cov_last_quad,cov_published,cov_last_reset,cov_queued_fault);
        $display("SCATTER4 strengthened coverage slow_empty=%0d lower_read=%0d last_frame_request=%0d last_frame_pending=%0d last_frame_out_stall=%0d last_frame_refill=%0d",
            cov_slow_empty,cov_lower_read,cov_last_frame_request,cov_last_frame_pending,
            cov_last_frame_out_stall,cov_last_frame_refill);
        $display("PASS SCATTER4 independent directed regression: INDEX7 WIDTH256 HEIGHT128, real FIFO2 wrapper,parameterized groups/128pixels, dual-write parity memories and non-vacuous pressure");
        $finish;
    end
    initial begin #8000000;$fatal(1,"SCATTER4 directed regression bounded timeout");end
    wire [0:0] ref_frame_ready;
    wire [0:0] ref_in_ready;
    wire [0:0] ref_out_valid;
    wire [23:0] ref_p00;
    wire [23:0] ref_p10;
    wire [23:0] ref_p01;
    wire [23:0] ref_p11;
    wire [7:0] ref_fx;
    wire [7:0] ref_fy;
    wire [24:0] ref_out_tag;
    wire [27:0] ref_araddr;
    wire [3:0] ref_arlen;
    wire [0:0] ref_arvalid;
    wire [0:0] ref_failed;
    wire [7:0] ref_fault;
    wire [31:0] ref_hits;
    wire [31:0] ref_misses;
    wire [31:0] ref_completed_queries;
    ddr_neighbour_cache_scatter4_tag_prefetch_local_reference #(.WIDTH(WIDTH),.HEIGHT(HEIGHT),.TAG_W(25),
        .INDEX_BITS(INDEX_BITS),.TIMEOUT_BITS(10)) reference_dut(
        .clk(clk),.rst_n(rst_n),.frame_valid(frame_valid),.frame_ready(ref_frame_ready),.frame_base(frame_base),
        .in_valid(in_valid),.in_ready(ref_in_ready),.in_x(in_x),.in_y(in_y),.in_tag(in_tag),
        .out_valid(ref_out_valid),.out_ready(out_ready),.p00(ref_p00),.p10(ref_p10),.p01(ref_p01),.p11(ref_p11),
        .fx(ref_fx),.fy(ref_fy),.out_tag(ref_out_tag),.araddr(ref_araddr),.arlen(ref_arlen),.arvalid(ref_arvalid),.arready(arready),
        .rdata(rdata),.rvalid(rvalid),.rlast(rlast),.rid(rid),.failed(ref_failed),.fault(ref_fault),
        .hits(ref_hits),.misses(ref_misses),.completed_queries(ref_completed_queries));
    // Both implementations receive identical inputs. Compare after NBA on
    // every cycle, including reset/fault and invalid output cycles.
    integer differential_cycles=0;
    integer known_valid_checks=0;
    always @(posedge clk)begin
        #1;
        differential_cycles=differential_cycles+1;
        if({frame_ready,in_ready,out_valid,p00,p10,p01,p11,fx,fy,out_tag,araddr,arlen,arvalid,failed,fault,hits,misses,completed_queries} !== {ref_frame_ready,ref_in_ready,ref_out_valid,ref_p00,ref_p10,ref_p01,ref_p11,ref_fx,ref_fy,ref_out_tag,ref_araddr,ref_arlen,ref_arvalid,ref_failed,ref_fault,ref_hits,ref_misses,ref_completed_queries})
            $fatal(1,"LOCKSTEP output mismatch cycle=%0d state=%0d",differential_cycles,dut.inner.state);
        if({dut.frame_loaded,dut.queue_count,dut.read_pointer,dut.write_pointer,
             dut.inner.state,dut.inner.valid_lines,dut.inner.selected_line,
             dut.inner.selected_block,dut.inner.address_pending,
             dut.inner.scatter_group,dut.inner.fill_beat,dut.inner.watchdog,
             dut.inner.query_valid,dut.inner.v0,dut.inner.v1} !==
           {reference_dut.frame_loaded,reference_dut.queue_count,reference_dut.read_pointer,reference_dut.write_pointer,
             reference_dut.inner.state,reference_dut.inner.valid_lines,reference_dut.inner.selected_line,
             reference_dut.inner.selected_block,reference_dut.inner.address_pending,
             reference_dut.inner.scatter_group,reference_dut.inner.fill_beat,reference_dut.inner.watchdog,
             reference_dut.inner.query_valid,reference_dut.inner.v0,reference_dut.inner.v1})
            $fatal(1,"LOCKSTEP internal state/valid-lines mismatch cycle=%0d",differential_cycles);
        if(rst_n && dut.inner.state==9 && dut.inner.valid_lines[dut.inner.selected_line])begin
            known_valid_checks=known_valid_checks+1;
            if((^dut.inner.tags[dut.inner.selected_line])===1'bx)
                $fatal(1,"valid line used an uninitialized tag");
        end
    end

    final begin
        $display("LOCKSTEP cycles=%0d known_valid_checks=%0d",differential_cycles,known_valid_checks);
    end

endmodule
