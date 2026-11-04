`timescale 1ns/1ps
// Independent sparse-query oracle. The identical test is executed against
// fill8 and frozen fill32; neither cache supplies the other's pixel oracle.
module directfill_tagpipe_cache_case #(parameter WIDTH=639,HEIGHT=480,INDEX_BITS=3)(output reg finished=0);
    localparam GROUPS=8;
    localparam STRIDE=1048576,LINES=1<<INDEX_BITS;
    reg clk=0;always #4 clk=~clk;
    reg rst_n=0,frame_valid=0,in_valid=0;
    reg [27:0] frame_base=0;
    reg signed [23:0] in_x=0,in_y=0;
    reg [24:0] in_tag=0;
    wire frame_ready,in_ready,out_valid,failed;
    wire [23:0] p00,p10,p01,p11;wire [7:0] fx,fy,fault;
    wire [24:0] out_tag;wire [27:0] araddr;wire [3:0] arlen;wire arvalid;
    reg arready=0,rvalid=0,rlast=0,out_ready=0;
    reg [255:0] rdata=0;reg [3:0] rid=0;
    wire [31:0] hits,misses,completed_queries;
    ddr_neighbour_cache_scatter16_rowpipe
      #(.WIDTH(WIDTH),.HEIGHT(HEIGHT),.INDEX_BITS(INDEX_BITS),.TAG_W(25),.TIMEOUT_BITS(8)) dut(
        .clk(clk),.rst_n(rst_n),.frame_valid(frame_valid),.frame_ready(frame_ready),.frame_base(frame_base),
        .in_valid(in_valid),.in_ready(in_ready),.in_x(in_x),.in_y(in_y),.in_tag(in_tag),
        .out_valid(out_valid),.out_ready(out_ready),.p00(p00),.p10(p10),.p01(p01),.p11(p11),
        .fx(fx),.fy(fy),.out_tag(out_tag),.araddr(araddr),.arlen(arlen),.arvalid(arvalid),.arready(arready),
        .rdata(rdata),.rvalid(rvalid),.rlast(rlast),.rid(rid),.failed(failed),.fault(fault),
        .hits(hits),.misses(misses),.completed_queries(completed_queries));
    integer ticks=0,left=0,beat=0,burst_pixel=0,burst_epoch=0,burst_bank=0;
    integer active_epoch=0,active_bank=0,sent=0,received=0;
    integer mode=0,commit_count=0,fill_count=0,ram_checks=0,normal_outputs=0;
    integer ar_stalls=0,r_gaps=0,out_stalls=0,in_stalls=0,queue_full=0,frame_pending=0;
    integer fast_queries=0,slow_queries=0,frame_drains=0,reset_last=0,fault_cases=0;
    integer same_cycle_first_beats=0;
    integer total_bursts=0,commit_cycles=0,stream_first=-1,stream_last=-1;
    integer trace,delayed_first_beats=0,continuous_commit_pairs=0;
    reg previous_good_rx=0,previous_rx_last=0;
    reg [2:0] previous_rx_beat=0;
    reg [INDEX_BITS-1:0] previous_rx_line=0;
    reg previous_commit=0;
    integer stream_accept=-1,stream_latency=-1,stream_outputs=0,warm_bursts=0;
    reg checking=1,force_ar_stall=0,force_output_stall=0,unthrottled=0,stream_phase=0,delayed_return=0,continuous_return=0;
    reg held=0,held_ar=0;
    reg [136:0] expected[0:2047],held_value;
    reg [31:0] held_address;
    function automatic [15:0] source_word(input integer pos,bank,epoch);
        source_word=(pos*109+(pos>>3)*53+(pos^(pos>>9))*17+16'hac37+bank*16'h2513+epoch*16'h149b)&65535;
    endfunction
    function automatic [23:0] pixel(input integer x,y,bank,epoch);
        reg [15:0] p;
        begin
            if(x<0||x>=WIDTH||y<0||y>=HEIGHT)pixel=0;
            else begin p=source_word(y*WIDTH+x,bank,epoch);
                pixel={p[15:11],p[15:13],p[10:5],p[10:9],p[4:0],p[4:2]};end
        end
    endfunction
    always @(negedge clk)begin
        arready=rst_n&&!force_ar_stall&&left==0&&ticks%7>=2;
        rvalid=rst_n&&left>0&&(continuous_return||ticks%5!=0);
        rlast=left==1;rid=0;
        if(mode==1&&beat==3)rid=9;
        if(mode==2&&beat==3)rlast=1;
        if(mode==3&&left==1)rlast=0;
        if(mode==4&&left==0&&rst_n)begin rvalid=1;rlast=1;end
        if(mode==6)rvalid=0;
        for(integer n=0;n<16;n=n+1)rdata[n*16+:16]=source_word(burst_pixel+beat*16+n,burst_bank,burst_epoch);
        // Independent zero-latency first beat on the actual AR handshake.
        // Remaining seven beats retain the existing gaps and error injection.
        if(arvalid&&arready&&mode!=6&&!delayed_return)begin
            rvalid=1;rlast=0;rid=0;
            for(integer n=0;n<16;n=n+1)
                rdata[n*16+:16]=source_word((araddr-(araddr>=STRIDE?STRIDE:0))*2+n,active_bank,active_epoch);
        end
        out_ready=rst_n&&!force_output_stall&&(unthrottled||ticks%11>=3);
    end
    always @(posedge clk)begin
        ticks=ticks+1;
        if(!rst_n)begin
            left<=0;beat<=0;sent<=0;received<=0;active_epoch<=0;active_bank<=0;
            held<=0;held_ar<=0;commit_count=0;previous_good_rx<=0;previous_commit<=0;
        end else begin
            if(held_ar&&(!arvalid||{araddr,arlen}!==held_address))$fatal(1,"AR unstable WIDTH%0d",WIDTH);
            held_ar<=arvalid&&!arready;held_address<={araddr,arlen};
            if(arvalid&&!arready)ar_stalls=ar_stalls+1;
            if(left>0&&!rvalid)r_gaps=r_gaps+1;
            if(in_valid&&!in_ready)in_stalls=in_stalls+1;
            if(dut.queue_count==2)queue_full=queue_full+1;
            if(frame_valid&&!frame_ready)frame_pending=frame_pending+1;
            if(dut.inner.accept_fast)fast_queries=fast_queries+1;
            if(dut.inner.accept_slow)slow_queries=slow_queries+1;
            if(frame_valid&&in_ready)$fatal(1,"new query admitted during pending frame");
            if(frame_valid&&frame_ready)begin
                if(sent!=received||left!=0||out_valid||dut.queue_count!=0)$fatal(1,"frame accepted before complete drain");
                active_bank<=frame_base>=STRIDE;active_epoch<=active_epoch+1;frame_drains=frame_drains+1;
            end
            if(checking)begin
                if(failed)$fatal(1,"unexpected fault %h width%0d",fault,WIDTH);
                if(held&&(!out_valid||{p00,p10,p01,p11,fx,fy,out_tag}!==held_value))$fatal(1,"result unstable under stall");
                if(in_valid&&in_ready)begin
                    expected[sent]<={pixel($signed(in_x)>>>8,$signed(in_y)>>>8,active_bank,active_epoch),
                        pixel(($signed(in_x)>>>8)+1,$signed(in_y)>>>8,active_bank,active_epoch),
                        pixel($signed(in_x)>>>8,($signed(in_y)>>>8)+1,active_bank,active_epoch),
                        pixel(($signed(in_x)>>>8)+1,($signed(in_y)>>>8)+1,active_bank,active_epoch),
                        in_x[7:0],in_y[7:0],in_tag};
                    $fdisplay(trace,"Q %0d %0d %0d %0d %0d",$signed(in_x),$signed(in_y),in_tag,active_bank,active_epoch);
                    sent<=sent+1;
                    if(stream_phase&&stream_accept<0)stream_accept=ticks;
                end
                if(out_valid&&!out_ready)out_stalls=out_stalls+1;
                if(out_valid&&out_ready)begin
                    if(received>=sent||{p00,p10,p01,p11,fx,fy,out_tag}!==expected[received])
                        $fatal(1,"independent pixel/metadata oracle WIDTH%0d output%0d tag%h got%h expected%h",WIDTH,received,out_tag,{p00,p10,p01,p11,fx,fy,out_tag},expected[received]);
                    $fdisplay(trace,"O %06h %06h %06h %06h %02h %02h %07h",p00,p10,p01,p11,fx,fy,out_tag);
                    received<=received+1;normal_outputs=normal_outputs+1;
                    if(stream_phase)begin
                        if(stream_first<0)stream_first=ticks;
                        stream_last=ticks;stream_outputs=stream_outputs+1;
                    end
                end
            end
            held<=checking&&out_valid&&!out_ready;held_value<={p00,p10,p01,p11,fx,fy,out_tag};
            if(arvalid&&arready)begin
                if(left!=0||arlen!=7||araddr[5:0]!=0||(araddr>=STRIDE)!=active_bank)$fatal(1,"invalid burst reservation");
                burst_pixel<=(araddr-(araddr>=STRIDE?STRIDE:0))*2;
                burst_bank<=active_bank;burst_epoch<=active_epoch;
                left<=rvalid?7:8;beat<=rvalid?1:0;total_bursts=total_bursts+1;
                if(rvalid)begin
                    if(dut.inner.state!=2||dut.inner.fill_beat!=0)$fatal(1,"same-cycle first beat did not arrive at AR/beat0");
                    same_cycle_first_beats=same_cycle_first_beats+1;
                end else delayed_first_beats=delayed_first_beats+1;
            end
            if(rvalid&&left>0)begin left<=left-1;beat<=beat+1;end
            previous_commit<=dut.inner.write_commit;
            previous_good_rx<=!failed && rvalid && dut.inner.receiving && rid==0 && rlast==(dut.inner.fill_beat==7);
            previous_rx_beat<=dut.inner.fill_beat;
            previous_rx_line<=dut.inner.selected_line;
            previous_rx_last<=dut.inner.fill_beat==7;
            // The accepted, valid receive is the only authority for next-edge
            // RAM commit. No combinational DDR payload feeds a RAM input.
            if(checking)begin
                if(dut.inner.write_commit!==previous_good_rx)
                    $fatal(1,"RX/commit ownership delay mismatch WIDTH%0d INDEX%0d",WIDTH,INDEX_BITS);
                if(dut.inner.write_commit)begin
                    if(dut.inner.write_commit_beat!==previous_rx_beat ||
                       dut.inner.write_commit_line!==previous_rx_line ||
                       dut.inner.write_commit_last!==previous_rx_last)
                        $fatal(1,"registered commit metadata differs");
                    if(dut.inner.write_commit_beat!==commit_count ||
                       dut.inner.valid_lines[dut.inner.write_commit_line]!==0)
                        $fatal(1,"direct fill ordinal/early tag publication mismatch");
                    if(dut.inner.read_enable||dut.inner.read_lower)
                        $fatal(1,"direct write and RAM read overlap");
                    if(previous_commit)continuous_commit_pairs=continuous_commit_pairs+1;
                    commit_count=commit_count+1;commit_cycles=commit_cycles+1;
                    if(dut.inner.write_commit_last)begin
                        if(commit_count!=8 || dut.inner.state!=4)
                            $fatal(1,"last commit missing wait/complete beat count");
                        #1;
                        if(dut.inner.valid_lines[dut.inner.write_commit_line]!==1 ||
                           dut.inner.tags[dut.inner.write_commit_line]!==dut.inner.fill_write_block)
                            $fatal(1,"last actual RAM commit did not publish line");
                        for(integer p=0;p<128;p=p+1)begin
                            if(p%2==0)begin
                                if(dut.inner.even_pixels[dut.inner.write_commit_line*16+p/8][((p/2)%4)*16+:16]!==source_word(burst_pixel+p,burst_bank,burst_epoch))
                                    $fatal(1,"direct even RAM lane mismatch p%0d",p);
                            end else if(dut.inner.odd_pixels[dut.inner.write_commit_line*16+p/8][((p/2)%4)*16+:16]!==source_word(burst_pixel+p,burst_bank,burst_epoch))
                                $fatal(1,"direct odd RAM lane mismatch p%0d",p);
                            ram_checks=ram_checks+1;
                        end
                        fill_count=fill_count+1;commit_count=0;
                    end
                end
            end
            #1;
            if(stream_phase&&stream_accept>=0&&stream_latency<0&&out_valid)stream_latency=ticks-stream_accept;
        end
    end
    // Independent stage/metadata checks at the actual transaction edges.
    integer lookup_miss_overlap=0,query_refreshes=0,stale_valid_refreshes=0;
    integer result_stall_metadata_cycles=0,slow_lookup_cycles=0,choose_cycles=0;
    reg monitor_stall,monitor_refresh;
    reg [78:0] saved_query_payload;
    reg [24:0] saved_cached_tag[0:3],expected_refresh_tag[0:3];
    reg [3:0] saved_cached_valid,expected_refresh_valid;
    reg [31:0] saved_query_number[0:3];
    reg [INDEX_BITS-1:0] saved_query_index[0:3];
    always @(posedge clk)if(rst_n&&checking&&!failed)begin
        monitor_stall=dut.inner.state==7&&!out_ready&&dut.inner.query_valid;
        monitor_refresh=dut.inner.consume_slow&&dut.inner.query_valid;
        if(dut.inner.pre_to_query&&dut.inner.accept_slow)lookup_miss_overlap=lookup_miss_overlap+1;
        if(dut.inner.state==10)slow_lookup_cycles=slow_lookup_cycles+1;
        if(dut.inner.state==11)choose_cycles=choose_cycles+1;
        if(frame_valid&&frame_ready&&(dut.inner.decoded_count!=0||dut.inner.query_valid||dut.inner.pre_valid))
            $fatal(1,"frame accepted with old decoded/query epoch");
        saved_query_payload={dut.inner.query_x,dut.inner.query_y,dut.inner.query_fx,dut.inner.query_fy,dut.inner.query_tag,dut.inner.in_bounds};
        saved_cached_valid=dut.inner.query_cached_valid;
        for(integer n=0;n<4;n=n+1)begin
            saved_cached_tag[n]=dut.inner.query_cached_tag[n];
            saved_query_number[n]=dut.inner.pixel_number[n];
            saved_query_index[n]=dut.inner.query_line_index[n];
            expected_refresh_tag[n]=dut.inner.tags[dut.inner.query_line_index[n]];
            expected_refresh_valid[n]=dut.inner.valid_lines[dut.inner.query_line_index[n]];
        end
        if(monitor_stall)result_stall_metadata_cycles=result_stall_metadata_cycles+1;
        if(monitor_refresh)begin
            query_refreshes=query_refreshes+1;
            if(dut.inner.write_commit)$fatal(1,"query refresh collided with uncommitted fill");
            for(integer n=0;n<4;n=n+1)
                if(saved_cached_valid[n]&&saved_cached_tag[n]!==expected_refresh_tag[n])
                    stale_valid_refreshes=stale_valid_refreshes+1;
        end
        #1;
        if(monitor_stall)begin
            if({dut.inner.query_x,dut.inner.query_y,dut.inner.query_fx,dut.inner.query_fy,dut.inner.query_tag,dut.inner.in_bounds}!==saved_query_payload||
               dut.inner.query_cached_valid!==saved_cached_valid)$fatal(1,"RESULT stall changed held query/metadata");
            for(integer n=0;n<4;n=n+1)
                if(dut.inner.query_cached_tag[n]!==saved_cached_tag[n]||dut.inner.pixel_number[n]!==saved_query_number[n]||
                   dut.inner.query_line_index[n]!==saved_query_index[n])$fatal(1,"RESULT stall changed held neighbour/index/tag");
        end
        if(monitor_refresh)begin
            if(dut.inner.query_cached_valid!==expected_refresh_valid)$fatal(1,"RESULT consumption did not refresh valid bits");
            for(integer n=0;n<4;n=n+1)
                if(dut.inner.query_cached_tag[n]!==expected_refresh_tag[n])$fatal(1,"RESULT consumption did not refresh replaced tag");
        end
    end
    // Second-way metadata is a complete peer of the frozen way0 monitor.
    reg [24:0] held_way1_tag[0:3],refresh_way1_tag[0:3];
    reg [3:0] held_way1_valid,refresh_way1_valid;
    always @(posedge clk)if(rst_n&&checking&&!failed)begin
        held_way1_valid=dut.inner.query_cached_valid_way1;
        for(integer n=0;n<4;n=n+1)begin
            held_way1_tag[n]=dut.inner.query_cached_tag_way1[n];
            refresh_way1_tag[n]=dut.inner.tags[(1<<(INDEX_BITS-1))+dut.inner.query_line_index[n]];
            refresh_way1_valid[n]=dut.inner.valid_lines[(1<<(INDEX_BITS-1))+dut.inner.query_line_index[n]];
        end
        #1;
        if(monitor_stall)begin
            if(dut.inner.query_cached_valid_way1!==held_way1_valid)$fatal(1,"stalled way1 valid changed");
            for(integer n=0;n<4;n=n+1)
                if(dut.inner.query_cached_tag_way1[n]!==held_way1_tag[n])$fatal(1,"stalled way1 tag changed");
        end
        if(monitor_refresh)begin
            if(dut.inner.query_cached_valid_way1!==refresh_way1_valid)$fatal(1,"way1 refresh valid mismatch");
            for(integer n=0;n<4;n=n+1)
                if(dut.inner.query_cached_tag_way1[n]!==refresh_way1_tag[n])$fatal(1,"way1 refresh tag mismatch");
        end
    end
    // Independent replacement oracle: full block IDs, serial demand order,
    // invalid-first selection and one-bit LRU. Does not use DUT cached tags.
    localparam SETS=LINES/2;
    reg [LINES-1:0] oracle_valid=0;
    reg [24:0] oracle_tag[0:LINES-1];
    reg [SETS-1:0] oracle_lru=0;
    integer oracle_set,oracle_way,oracle_line,oracle_block;
    integer oracle_checks=0,way0_fills=0,way1_fills=0,fast_way1_touches=0;
    integer invalid0_choices=0,invalid1_choices=0,lru0_choices=0,lru1_choices=0;
    reg oracle_hit;
    always @(posedge clk)begin
        if(!rst_n || (frame_valid&&frame_ready))begin oracle_valid=0;oracle_lru=0;end
        else if(checking&&!failed)begin
            if(dut.inner.accept_fast)begin
                for(integer n=0;n<4;n=n+1)if(dut.inner.in_bounds[n])begin
                    oracle_block=dut.inner.pixel_number[n]>>7;oracle_set=oracle_block&(SETS-1);
                    if(oracle_valid[oracle_set]&&oracle_tag[oracle_set]==oracle_block)oracle_way=0;
                    else if(oracle_valid[oracle_set+SETS]&&oracle_tag[oracle_set+SETS]==oracle_block)oracle_way=1;
                    else $fatal(1,"DUT fast hit absent from independent full-tag cache");
                    if(dut.inner.query_hit_way[n]!==oracle_way[0])$fatal(1,"fast hit selected wrong physical way");
                    if(dut.inner.pixel_address[n]!==((oracle_way*SETS+oracle_set)*64+((dut.inner.pixel_number[n]&127)>>1)))
                        $fatal(1,"fast physical pixel address disagrees with full-tag oracle");
                    oracle_lru[oracle_set]=!oracle_way[0];
                    if(oracle_way)fast_way1_touches=fast_way1_touches+1;
                end
            end
            if(dut.inner.state==9)begin
                oracle_block=dut.inner.selected_block;oracle_set=oracle_block&(SETS-1);oracle_hit=1;
                if(oracle_valid[oracle_set]&&oracle_tag[oracle_set]==oracle_block)oracle_way=0;
                else if(oracle_valid[oracle_set+SETS]&&oracle_tag[oracle_set+SETS]==oracle_block)oracle_way=1;
                else begin
                    oracle_hit=0;
                    if(!oracle_valid[oracle_set])begin oracle_way=0;invalid0_choices=invalid0_choices+1;end
                    else if(!oracle_valid[oracle_set+SETS])begin oracle_way=1;invalid1_choices=invalid1_choices+1;end
                    else begin oracle_way=oracle_lru[oracle_set];
                        if(oracle_way)lru1_choices=lru1_choices+1;else lru0_choices=lru0_choices+1;end
                end
                oracle_line=oracle_way*SETS+oracle_set;oracle_checks=oracle_checks+1;
                if(dut.inner.selected_hit!==oracle_hit || dut.inner.selected_choose_line!==oracle_line[INDEX_BITS-1:0])
                    $fatal(1,"independent invalid-first/LRU choice mismatch block%0d wantedline%0d gotline%0d",oracle_block,oracle_line,dut.inner.selected_choose_line);
                if(oracle_hit)oracle_lru[oracle_set]=!oracle_way[0];
                else oracle_valid[oracle_line]=0;
            end
            if(dut.inner.state==4&&dut.inner.write_commit_last)begin
                oracle_line=dut.inner.write_commit_line;oracle_set=oracle_line&(SETS-1);
                oracle_tag[oracle_line]=dut.inner.fill_write_block;oracle_valid[oracle_line]=1;
                oracle_lru[oracle_set]=!(oracle_line>=SETS);
                if(oracle_line>=SETS)way1_fills=way1_fills+1;else way0_fills=way0_fills+1;
            end
            #1;
            if(!failed && (dut.inner.valid_lines!==oracle_valid || dut.inner.lru_way!==oracle_lru))
                $fatal(1,"published metadata/LRU differs from independent ordered-demand oracle");
        end
    end
    task automatic reset_case;
        begin
            @(negedge clk);rst_n=0;frame_valid=0;in_valid=0;mode=0;
            force_ar_stall=0;force_output_stall=0;unthrottled=0;checking=1;delayed_return=0;continuous_return=0;
            repeat(4)@(negedge clk);rst_n=1;repeat(2)@(negedge clk);
            if(failed||out_valid||arvalid||dut.inner.valid_lines!=0)$fatal(1,"reset not clean");
        end
    endtask
    task automatic new_frame(input integer bank);
        begin
            @(negedge clk);frame_base=bank*STRIDE;frame_valid=1;
            do @(posedge clk);while(!frame_ready);
            @(negedge clk);frame_valid=0;repeat(2)@(negedge clk);
            if(dut.inner.valid_lines!=0)$fatal(1,"new frame retained cache lines");
        end
    endtask
    task automatic query(input integer x,y,fracx,fracy,tag);
        begin
            @(negedge clk);in_x=x*256+fracx;in_y=y*256+fracy;in_tag=tag;in_valid=1;
            do @(posedge clk);while(!in_ready);
            @(negedge clk);in_valid=0;
        end
    endtask
    task automatic drain;
        begin
            wait(sent==received&&!out_valid&&dut.queue_count==0&&dut.inner.frame_ready);
            repeat(3)@(negedge clk);
            if(left!=0||completed_queries!=received)$fatal(1,"final drain accounting mismatch");
        end
    endtask
    task automatic fault_case(input integer kind,input [7:0] expected_fault);
        begin
            reset_case();new_frame(0);checking=0;mode=kind;
            if(kind==5)force_ar_stall=1;
            if(kind!=4)query(126,1,31,229,25'h1001234);
            wait(failed);@(negedge clk);
            if(fault!==expected_fault||in_ready||frame_ready||out_valid)$fatal(1,"fault quarantine mismatch kind%0d",kind);
            repeat(20)@(negedge clk);
            if(!failed||fault!==expected_fault||in_ready||frame_ready||out_valid)$fatal(1,"fault not sticky");
            if(kind==5&&!arvalid)$fatal(1,"stalled AR withdrawn after timeout");
            fault_cases=fault_cases+1;
        end
    endtask
    integer summary,before_bursts,conflict_number;
    initial begin
        trace=$fopen($sformatf("trace-%0d-i%0d.txt",WIDTH,INDEX_BITS),"w");
        reset_case();new_frame(0);
        // Every low word lane, parity, 8/16/128-pixel boundary and odd-width
        // row transition gets its own four-neighbour reference calculation.
        for(integer x=0;x<145;x=x+1)query(x,0,(x*37+11)&255,(x*73+5)&255,25'h1000000+x);
        query(-1,-1,255,255,17);query(-1,0,1,2,18);query(0,-1,3,4,19);
        query(WIDTH-1,HEIGHT-1,255,255,20);query(WIDTH-1,0,5,6,21);
        query(0,HEIGHT-1,7,8,22);query(WIDTH,HEIGHT,0,0,23);
        query(-32768,-32768,0,0,24);query(32767,32767,255,255,25);drain();
        conflict_number=1<<(INDEX_BITS+7);
        for(integer q=0;q<12;q=q+1)begin
            if(q%2==0)query(0,0,q,q*3,100+q);
            else query(conflict_number%WIDTH,conflict_number/WIDTH,q,q*3,100+q);
        end
        drain();
        delayed_return=1;
        for(integer q=0;q<32;q=q+1)query(257+q*7,3+q*3,(q*13)&255,(q*17)&255,25'h1010000+q);
        drain();delayed_return=0;continuous_return=1;
        for(integer q=0;q<32;q=q+1)query(129+q*11,67+q*7,(q*29)&255,(q*31)&255,25'h1020000+q);
        drain();continuous_return=0;
        // An already-hot A is followed by cold B at the same cache indices,
        // with a younger A looked up on B's miss edge. B replaces A's tags;
        // hold RESULT, then consume it and require the held A to re-lookup.
        new_frame(0);
        query(0,0,7,11,25'h10e0000);drain();
        query((2*conflict_number)%WIDTH,(2*conflict_number)/WIDTH,13,17,25'h10e0001);drain();
        force_output_stall=1;unthrottled=1;
        fork
            begin
                @(negedge clk);in_valid=1;
                for(integer q=0;q<3;q=q+1)begin
                    in_x=(q==0?conflict_number%WIDTH:0)*256+17;
                    in_y=(q==0?conflict_number/WIDTH:0)*256+29;
                    in_tag=25'h10e1000+q;
                    do @(posedge clk);while(!in_ready);
                    @(negedge clk);
                end
                in_valid=0;
            end
            begin wait(dut.inner.state==7&&dut.inner.query_valid);repeat(20)@(negedge clk);force_output_stall=0;end
        join
        drain();unthrottled=0;
        // Warm the exact lane-varying region, then prove latency and II=1.
        for(integer q=0;q<64;q=q+1)query(q+2,0,(q*3)&255,(q*7)&255,200+q);
        drain();before_bursts=total_bursts;unthrottled=1;stream_phase=1;
        @(negedge clk);in_valid=1;
        for(integer q=0;q<64;q=q+1)begin
            in_x=(q+2)*256+((q*41+3)&255);in_y=(q*67+13)&255;in_tag=25'h1001000+q;
            do @(posedge clk);while(!in_ready);
            @(negedge clk);
        end
        in_valid=0;drain();stream_phase=0;
        if(total_bursts!=before_bursts||stream_outputs!=64||stream_last-stream_first!=63||stream_latency!=5)
            $fatal(1,"warm throughput/latency mismatch fills%0d outputs%0d span%0d latency%0d",total_bursts-before_bursts,stream_outputs,stream_last-stream_first,stream_latency,lookup_miss_overlap,query_refreshes,stale_valid_refreshes,result_stall_metadata_cycles,slow_lookup_cycles);
        // Hold a complete result while distinct queued metadata fills every
        // elastic stage, then request a new bank before the old frame drains.
        force_output_stall=1;unthrottled=0;
        fork
            begin for(integer q=0;q<24;q=q+1)query(10+q,0,(q*19)&255,(q*43)&255,300+q);end
            begin wait(out_valid&&!out_ready);repeat(30)@(negedge clk);force_output_stall=0;end
        join
        force_output_stall=1;
        fork
            begin new_frame(1);end
            begin repeat(25)@(negedge clk);force_output_stall=0;end
        join
        query(2,0,77,99,400);drain();new_frame(1);query(2,0,31,19,401);drain();
        // Reset exactly before the last direct write. An incomplete block
        // must never publish or survive reset, even at the same base address.
        new_frame(0);query(127,1,1,2,500);
        wait(dut.inner.fill_write_valid&&dut.inner.fill_write_beat==7);
        @(negedge clk);rst_n=0;in_valid=0;frame_valid=0;reset_last=reset_last+1;
        repeat(4)@(negedge clk);rst_n=1;repeat(2)@(negedge clk);
        if(dut.inner.valid_lines!=0||out_valid)$fatal(1,"last-commit reset leaked partial line/output");
        new_frame(0);query(127,1,3,4,501);drain();
        fault_case(1,8'h03);fault_case(2,8'h03);fault_case(3,8'h03);
        fault_case(4,8'h04);fault_case(5,8'h01);fault_case(6,8'h01);
        reset_case();new_frame(0);query(7,1,1,255,600);drain();
        if(fill_count<10||ram_checks!=fill_count*128||ar_stalls==0||r_gaps==0||out_stalls==0||in_stalls==0||
           queue_full==0||frame_pending==0||fast_queries==0||slow_queries==0||reset_last!=1||fault_cases!=6||same_cycle_first_beats==0||delayed_first_beats==0||continuous_commit_pairs==0||lookup_miss_overlap==0||query_refreshes==0||stale_valid_refreshes==0||result_stall_metadata_cycles==0||slow_lookup_cycles==0)
            $fatal(1,"mandatory coverage was vacuous");
        if(oracle_checks<10||way0_fills==0||way1_fills==0||fast_way1_touches==0||invalid0_choices==0||invalid1_choices==0||lru0_choices+lru1_choices==0)
            $fatal(1,"associative replacement coverage was vacuous");
        $display("ASSOC_ORACLE WIDTH%0d INDEX%0d checks%0d fillways%0d/%0d fastway1%0d invalid%0d/%0d lru%0d/%0d",WIDTH,INDEX_BITS,oracle_checks,way0_fills,way1_fills,fast_way1_touches,invalid0_choices,invalid1_choices,lru0_choices,lru1_choices);
        if(choose_cycles!=slow_lookup_cycles)$fatal(1,"each normal lookup must execute one CHOOSE");
        $display("CHOOSE_CYCLES WIDTH%0d INDEX%0d cycles%0d",WIDTH,INDEX_BITS,choose_cycles);
        summary=$fopen($sformatf("summary-%0d-i%0d.json",WIDTH,INDEX_BITS),"w");
        $fdisplay(summary,"{\"passed\":true,\"width\":%0d,\"height\":%0d,\"index_bits\":%0d,\"commits_per_fill\":8,\"same_cycle_first_beats\":%0d,\"delayed_first_beats\":%0d,\"continuous_commit_pairs\":%0d,\"complete_fills\":%0d,\"ram_pixels_checked\":%0d,\"normal_outputs\":%0d,\"ar_stalls\":%0d,\"r_gaps\":%0d,\"output_stalls\":%0d,\"input_stalls\":%0d,\"queue_full\":%0d,\"frame_pending\":%0d,\"fast_queries\":%0d,\"slow_queries\":%0d,\"frame_drains\":%0d,\"reset_before_last_commit\":%0d,\"fault_cases\":%0d,\"warm_stream_outputs\":%0d,\"warm_span_cycles\":%0d,\"warm_first_valid_latency\":%0d,\"lookup_miss_overlap\":%0d,\"query_refreshes\":%0d,\"stale_valid_refreshes\":%0d,\"result_stall_metadata_cycles\":%0d,\"slow_lookup_cycles\":%0d}",
          WIDTH,HEIGHT,INDEX_BITS,same_cycle_first_beats,delayed_first_beats,continuous_commit_pairs,fill_count,ram_checks,normal_outputs,ar_stalls,r_gaps,out_stalls,in_stalls,queue_full,frame_pending,fast_queries,slow_queries,frame_drains,reset_last,fault_cases,stream_outputs,stream_last-stream_first,stream_latency,lookup_miss_overlap,query_refreshes,stale_valid_refreshes,result_stall_metadata_cycles,slow_lookup_cycles);
        $fclose(summary);$fclose(trace);
        $display("PASS DIRECTFILL independent WIDTH%0d INDEX%0d fills%0d outputs%0d faults%0d",WIDTH,INDEX_BITS,fill_count,normal_outputs,fault_cases);finished=1;
    end
    initial begin #20000000;$fatal(1,"bounded cache case timeout WIDTH%0d",WIDTH);end
endmodule
module tb_directfill_tagpipe_cache;
    wire small16_done,small32_done,native_done;
    directfill_tagpipe_cache_case #(.WIDTH(2048),.HEIGHT(480),.INDEX_BITS(5)) small16(small16_done);
    directfill_tagpipe_cache_case #(.WIDTH(639),.HEIGHT(480),.INDEX_BITS(6)) small32(small32_done);
    directfill_tagpipe_cache_case #(.WIDTH(1920),.HEIGHT(1080),.INDEX_BITS(10)) native1024(native_done);
    initial begin wait(small16_done&&small32_done&&native_done);
        $display("PASS TAGPIPE complete independent cache regression");$finish;end
    initial begin #20000000;$fatal(1,"associative regression timeout");end
endmodule
