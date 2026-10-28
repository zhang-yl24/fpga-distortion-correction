// NEW CANDIDATE UNIT ONLY: sparse1920 queries, no full-frame/native8/STA/device claim.
`timescale 1ns/1ps
// Compile ONLY the new SCATTER4 cache and this bench. No old-cache oracle.
// Data is computed independently from linear pixel number, bank and frame epoch.
module rowpipe_cache_exerciser(output reg finished=0);
    localparam WIDTH=1920,HEIGHT=1080,INDEX_BITS=7,LINES=1<<INDEX_BITS;
    localparam ADDRESS_BITS=INDEX_BITS+6,STRIDE=1048576;
    localparam CONFLICT_Y=128; //128*1920 pixels is an exact128-line cache-index wrap.
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
    ddr_neighbour_cache_scatter4_rowpipe #(.WIDTH(WIDTH),.HEIGHT(HEIGHT),.TAG_W(25),
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
    reg checking=1,force_ar_stall=0,force_output_stall=0,fast_unthrottled=0;
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
    integer metadata_phase=0,metadata_inputs=0,metadata_all_field_changes=0;
    integer metadata_warm_outputs=0,metadata_warm_first=-1,metadata_warm_last=-1;
    integer metadata_stalled_outputs=0,metadata_mixed_outputs=0;
    integer metadata_input_stall=0,metadata_output_hold=0,metadata_pre_hold=0,metadata_query_hold=0;
    integer metadata_fast_queries=0,metadata_slow_queries=0,metadata_hit_miss_switches=0;
    reg metadata_previous_valid=0,metadata_mixed_previous_valid=0,metadata_previous_slow=0;
    reg signed [23:0] metadata_previous_x,metadata_previous_y;
    reg [24:0] metadata_previous_tag;

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
        out_ready=rst_n && !force_output_stall && (fast_unthrottled || ticks%11>=3);
    end

    // Sample after an earlier RAM-writing edge. This is intentionally not a
    // comparison against fill_buffer or another cache implementation.
    reg previous_scatter=0,previous_last=0,previous_frame=0,valid_history=0;
    reg [ADDRESS_BITS-1:0] previous_a,previous_b;
    reg [INDEX_BITS-1:0] previous_line;
    reg [24:0] previous_block,previous_old_tag;
    reg [15:0] previous_even_a,previous_odd_a,previous_even_b,previous_odd_b;
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
                    if(metadata_phase!=0)begin
                        metadata_inputs=metadata_inputs+1;
                        if(metadata_phase<=2 && metadata_previous_valid &&
                           in_x[23:8]!=metadata_previous_x[23:8] && in_y[23:8]!=metadata_previous_y[23:8] &&
                           in_x[7:0]!=metadata_previous_x[7:0] && in_y[7:0]!=metadata_previous_y[7:0] &&
                           in_tag!=metadata_previous_tag)
                            metadata_all_field_changes=metadata_all_field_changes+1;
                        metadata_previous_valid=1;metadata_previous_x=in_x;
                        metadata_previous_y=in_y;metadata_previous_tag=in_tag;
                    end
                end
                if(out_valid&&!out_ready)cov_out_stall=cov_out_stall+1;
                if(out_valid&&out_ready)begin
                    if(received>=sent || {p00,p10,p01,p11,fx,fy,out_tag}!==expected[received])
                        $fatal(1,"SCATTER4 independent four-neighbour oracle mismatch query%0d",received);
                    if(out_tag[24])cov_tag_high=cov_tag_high+1;else cov_tag_low=cov_tag_low+1;
                    received<=received+1;cov_normal_outputs=cov_normal_outputs+1;
                    case(metadata_phase)
                        1:begin
                            if(metadata_warm_outputs==0)metadata_warm_first=ticks;
                            metadata_warm_last=ticks;metadata_warm_outputs=metadata_warm_outputs+1;
                        end
                        2:metadata_stalled_outputs=metadata_stalled_outputs+1;
                        3:metadata_mixed_outputs=metadata_mixed_outputs+1;
                    endcase
                end
                if(metadata_phase==2)begin
                    if(in_valid&&!in_ready)metadata_input_stall=metadata_input_stall+1;
                    if(out_valid&&!out_ready)metadata_output_hold=metadata_output_hold+1;
                    if(dut.inner.pre_valid&&!dut.inner.pre_to_query)metadata_pre_hold=metadata_pre_hold+1;
                    if(dut.inner.query_valid&&!dut.inner.accept_query)metadata_query_hold=metadata_query_hold+1;
                end
                if(metadata_phase==3 && dut.inner.accept_query)begin
                    if(dut.inner.accept_fast)metadata_fast_queries=metadata_fast_queries+1;
                    if(dut.inner.accept_slow)metadata_slow_queries=metadata_slow_queries+1;
                    if(metadata_mixed_previous_valid && metadata_previous_slow!=dut.inner.accept_slow)
                        metadata_hit_miss_switches=metadata_hit_miss_switches+1;
                    metadata_mixed_previous_valid=1;metadata_previous_slow=dut.inner.accept_slow;
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
                        $fatal(1,"SCATTER4 last four writes did not publish valid/tag on the next observation edge");
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
            previous_last<=dut.inner.scatter_write&&dut.inner.scatter_group==31;
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
                if(dut.inner.scatter_group==31)begin
                    if(groups_in_fill!=32)$fatal(1,"SCATTER4 line did not take32 four-pixel groups");
                    cov_last_quad=cov_last_quad+1;
                end
                previous_a<=dut.inner.write_address_a;previous_b<=dut.inner.write_address_b;
                previous_line<=dut.inner.selected_line;previous_block<=dut.inner.selected_block;
                previous_old_tag<=dut.inner.tags[dut.inner.selected_line];
                previous_even_a<=word565(burst_pixel+4*dut.inner.scatter_group,burst_bank,burst_epoch);
                previous_odd_a<=word565(burst_pixel+4*dut.inner.scatter_group+1,burst_bank,burst_epoch);
                previous_even_b<=word565(burst_pixel+4*dut.inner.scatter_group+2,burst_bank,burst_epoch);
                previous_odd_b<=word565(burst_pixel+4*dut.inner.scatter_group+3,burst_bank,burst_epoch);
            end
        end
    end

    task automatic reset_all;
        begin
            @(negedge clk);rst_n=0;frame_valid=0;in_valid=0;mode=0;
            force_ar_stall=0;force_output_stall=0;fast_unthrottled=0;
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


    // Independent64-bit arithmetic reference observes actual candidate RTL
    // transfers, never another cache's output or DUT-produced expected data.
    reg [127:0] number_oracle[0:255];reg [3:0] bounds_oracle[0:255];
    reg [72:0] input_oracle[0:255];
    integer numeric_sent=0,numeric_built=0,cov_numeric_total=0;
    integer cov_pre_hold=0,cov_query_hold=0,cov_pre_refill=0,cov_query_refill=0,cov_pending_pre=0;
    reg pre_was_held=0,query_was_held=0;
    reg [110:0] held_pre;
    reg [206:0] held_query;
    wire [110:0] pre_bus={dut.inner.pre_row,dut.inner.pre_x,dut.inner.pre_y,
        dut.inner.pre_fx,dut.inner.pre_fy,dut.inner.pre_tag,dut.inner.pre_bounds};
    wire [206:0] query_bus={dut.inner.query_x,dut.inner.query_y,dut.inner.query_fx,dut.inner.query_fy,
        dut.inner.query_tag,dut.inner.in_bounds,dut.inner.pixel_number[0],dut.inner.pixel_number[1],
        dut.inner.pixel_number[2],dut.inner.pixel_number[3]};
    function automatic [31:0] reference_number(input signed [23:0] rx,ry,input integer which);
        longint signed xx,yy,number;
        begin xx=rx;yy=ry;xx=(xx>>>8)+(which%2);yy=(yy>>>8)+(which/2);
            number=yy*1920+xx;reference_number=number[31:0];end
    endfunction
    function automatic reference_bound(input signed [23:0] rx,ry,input integer which);
        longint signed xx,yy;
        begin xx=rx;yy=ry;xx=(xx>>>8)+(which%2);yy=(yy>>>8)+(which/2);
            reference_bound=xx>=0&&xx<1920&&yy>=0&&yy<1080;end
    endfunction
    reg build_observed;reg [127:0] check_numbers;reg [3:0] check_bounds;
    reg [72:0] check_input;integer observed_tick;
    integer latency_start=-1,first_latency=-1,stream_first=-1,stream_last=-1,stream_outputs=0;
    reg latency_active=0;
    always @(posedge clk)begin
        observed_tick=ticks;
        if(!rst_n)begin
            numeric_sent=0;numeric_built=0;pre_was_held=0;query_was_held=0;
        end else begin
            if(checking && pre_was_held && pre_bus!==held_pre)$fatal(1,"ROWPIPE pre row/XY/fraction/tag/bounds changed while stalled");
            if(checking && query_was_held && query_bus!==held_query)$fatal(1,"ROWPIPE decoded head changed while stalled");
            if(in_valid&&in_ready)begin
                if(numeric_sent>=256)$fatal(1,"ROWPIPE numerical scoreboard bound");
                for(integer n=0;n<4;n=n+1)begin
                    number_oracle[numeric_sent][n*32+:32]=reference_number(in_x,in_y,n);
                    bounds_oracle[numeric_sent][n]=reference_bound(in_x,in_y,n);
                end
                input_oracle[numeric_sent]={in_x,in_y,in_tag};numeric_sent=numeric_sent+1;
                if(latency_active && in_tag==25'h1abcde0)latency_start=observed_tick;
            end
            build_observed=dut.inner.pre_to_query;
            if(build_observed)begin
                if(numeric_built>=numeric_sent)$fatal(1,"ROWPIPE built without accepted input");
                check_numbers=number_oracle[numeric_built];check_bounds=bounds_oracle[numeric_built];
                check_input=input_oracle[numeric_built];numeric_built=numeric_built+1;
            end
            if(dut.inner.pre_valid&&!dut.inner.pre_to_query)cov_pre_hold=cov_pre_hold+1;
            if(dut.inner.query_valid&&!dut.inner.accept_query)cov_query_hold=cov_query_hold+1;
            if(dut.inner.pre_to_query&&dut.inner.decode_query)cov_pre_refill=cov_pre_refill+1;
            if(dut.inner.pre_to_query&&dut.inner.accept_query)cov_query_refill=cov_query_refill+1;
            if(frame_valid&&dut.inner.pre_valid)cov_pending_pre=cov_pending_pre+1;
            pre_was_held=dut.inner.pre_valid&&!dut.inner.pre_to_query;
            query_was_held=dut.inner.query_valid&&!dut.inner.accept_query;
            held_pre=pre_bus;held_query=query_bus;
            if(out_valid&&out_ready && out_tag>=25'h1800000 && out_tag<25'h1800040)begin
                if(stream_outputs==0)stream_first=observed_tick;
                stream_last=observed_tick;stream_outputs=stream_outputs+1;
            end
            #0.1;
            if(build_observed)begin
                for(integer n=0;n<4;n=n+1)
                    if(dut.inner.pixel_number[n]!==check_numbers[n*32+:32] || dut.inner.in_bounds[n]!==check_bounds[n])
                        $fatal(1,"ROWPIPE signed64 independent1920 neighbour number/bounds mismatch n%0d",n);
                if(dut.inner.query_x!=={check_input[72],check_input[72:57]} ||
                   dut.inner.query_y!=={check_input[48],check_input[48:33]} ||
                   dut.inner.query_fx!==check_input[56:49] || dut.inner.query_fy!==check_input[32:25] ||
                   dut.inner.query_tag!==check_input[24:0])$fatal(1,"ROWPIPE XY/fraction/TAG25 alignment mismatch");
                cov_numeric_total=cov_numeric_total+1;
            end
            if(latency_active && first_latency<0 && out_valid && out_tag==25'h1abcde0)
                first_latency=observed_tick-latency_start;
        end
    end
    integer summary;

    integer before_bursts,before_frames;
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

        query(-8388608,-8388608,25'h1000030);drain();
        query(8388607,8388607,25'h0000031);drain();
        query(1920*256,1080*256,25'h1000032);drain();
        query(-1,1079*256+255,25'h0000033);drain();
        query(1919*256+255,-1,25'h1000034);drain();
        $display("PASS ROWPIPE signed64 native1920 negative/extreme/partial-boundary arithmetic plus actual4pixel oracle");

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
        $display("PASS SCATTER4 INDEX7 full128-pixel parity/first-last, direct-map tag replacement, same/new bank epochs and TAG25 oracle");

        // Fill the real wrapper FIFO, hold a fourth request under full pressure,
        // then request the next frame while old queued work/results still exist.
        reset_all();select_frame(0);force_output_stall=1;
        query(127*256+1,0,25'h1000101);
        query(2*256+2,0,25'h0000102);
        query(3*256+3,0,25'h1000103);
        query(4*256+4,0,25'h0000104);
        wait(out_valid&&dut.queue_count==2);
        fork
            begin query(5*256+5,0,25'h1000105);end
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
        if(received!=5 || sent!=5 || dut.queue_count!=0 || completed_queries!=5)
            $fatal(1,"SCATTER4 frame_valid prevented old FIFO/query/results draining");
        query(17*256+19,43,25'h0000106);drain();
        $display("PASS SCATTER4 FIFO2 full input/output stalls, stable fractions/TAG25 and pending-frame drain");

        // Request the SAME bank immediately before its first line's final
        // scatter edge. Keep a new input offered, but forbid its admission;
        // old scatter, remaining neighbour loads and the held result must drain.
        reset_all();select_frame(0);force_output_stall=1;
        query(17*256+31,77,25'h1000181);
        wait(dut.inner.scatter_write&&dut.inner.scatter_group==31);
        @(negedge clk);
        if(!dut.inner.scatter_write || dut.inner.scatter_group!=31)
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
        $display("PASS SCATTER4 frame_valid at group31: no new input, exact old-result drain, same-bank invalidate and independent new-epoch refill");

        // Reset is sampled at the last scatter writing edge. RAM contents may
        // survive reset, but no partially written line may be published/reused.
        reset_all();select_frame(0);query(17*256+31,77,25'h1000201);
        wait(dut.inner.scatter_write&&dut.inner.scatter_group==31);
        @(negedge clk);
        if(!dut.inner.scatter_write || dut.inner.scatter_group!=31)$fatal(1,"SCATTER4 missed last-write reset point");
        cov_last_reset=cov_last_reset+1;
        rst_n=0;frame_valid=0;in_valid=0; // Assert BEFORE the group31 writing edge.
        reset_all();select_frame(0);before_bursts=bursts;
        query(17*256+31,77,25'h0000202);drain();
        if(bursts<=before_bursts)$fatal(1,"SCATTER4 partially scattered/reset RAM was reused without refilling");
        cov_reset_refill=cov_reset_refill+1;
        $display("PASS SCATTER4 reset on last four-pixel write edge, invalid metadata and mandatory refill");


        reset_all();select_frame(0);fast_unthrottled=1;
        query(17*256+29,77,25'h0000300);drain();
        latency_active=1;query(17*256+29,77,25'h1abcde0);drain();latency_active=0;
        if(first_latency!=4)$fatal(1,"ROWPIPE warmed public-input to first out_valid latency expected4 cycles got%0d",first_latency);
        @(negedge clk);in_valid=1;in_x=17*256+29;in_y=77;
        for(integer q=0;q<64;q=q+1)begin
            in_tag=25'h1800000+q;do @(posedge clk);while(!in_ready);
            @(negedge clk);
        end
        in_valid=0;drain();
        if(stream_outputs!=64 || stream_last-stream_first!=63)
            $fatal(1,"ROWPIPE warm hit pipeline did not sustain1 query/output per clock count%0d span%0d",stream_outputs,stream_last-stream_first);
        $display("PASS ROWPIPE warmed first-latency4 and64 consecutive actual outputs at1 per clock");

        // Vary every metadata field on adjacent accepted warm queries. The two
        // priming queries populate rows0/1/2 without a direct-map index alias;
        // the existing independent pixel/metadata scoreboard checks every output.
        reset_all();select_frame(0);fast_unthrottled=1;
        query(16*256,0,25'h0001000);drain();
        query(16*256,1*256,25'h0001001);drain();before_bursts=bursts;
        metadata_phase=1;
        @(negedge clk);in_valid=1;
        for(integer q=0;q<32;q=q+1)begin
            in_x=(16+q)*256+((q*37+11)&255);
            in_y=(q%2)*256+((q*53+7)&255);
            in_tag=25'h0020000+q+((q%2)*25'h1000000);
            do @(posedge clk);while(!in_ready);
            @(negedge clk);
        end
        in_valid=0;drain();metadata_phase=0;
        if(bursts!=before_bursts || metadata_warm_outputs!=32 || metadata_warm_last-metadata_warm_first!=31)
            $fatal(1,"ROWPIPE varying warm metadata did not sustain32 outputs/31 cycles without DDR refill");
        $display("PASS ROWPIPE varying warm metadata:32 distinct XY/fraction/TAG queries,32 outputs/31 cycles, independent four-neighbour scoreboard");

        // Fill all elastic stages with different queries while the first output
        // is held, then resume with periodic downstream stalls. Input metadata
        // stays fixed until each handshake, even when FIFO/pre/query are full.
        metadata_phase=2;fast_unthrottled=0;force_output_stall=1;
        fork
            begin
                @(negedge clk);in_valid=1;
                for(integer q=0;q<24;q=q+1)begin
                    in_x=(16+q)*256+((q*37+11)&255);
                    in_y=(q%2)*256+((q*53+7)&255);
                    in_tag=25'h0030000+q+((q%2)*25'h1000000);
                    do @(posedge clk);while(!in_ready);
                    @(negedge clk);
                end
                in_valid=0;
            end
            begin
                wait(out_valid&&!out_ready);repeat(12)@(negedge clk);
                force_output_stall=0;
            end
        join
        drain();metadata_phase=0;
        if(bursts!=before_bursts || metadata_stalled_outputs!=24 || metadata_all_field_changes!=55 ||
           metadata_input_stall==0 || metadata_output_hold==0 || metadata_pre_hold==0 || metadata_query_hold==0)
            $fatal(1,"ROWPIPE varying metadata backpressure/stage-hold coverage missing or warm cache refilled");
        $display("PASS ROWPIPE varying metadata backpressure:24 distinct queries,55 adjacent all-field changes, FIFO/pre/query/output holds and independent scoreboard");

        // row128 aliases row0's cache indices. Queue hit -> miss -> hit queries
        // with new fractions/tags, so the slow refill must drain the fast path
        // and resume it without shifting another query's coordinates or tags.
        metadata_phase=3;
        @(negedge clk);in_valid=1;
        for(integer q=0;q<12;q=q+1)begin
            in_x=(20+q)*256+((q*71+5)&255);
            in_y=((q%3==0) ? 0:CONFLICT_Y)*256+((q*97+3)&255);
            in_tag=25'h0040000+q+((q%2)*25'h1000000);
            do @(posedge clk);while(!in_ready);
            @(negedge clk);
        end
        in_valid=0;drain();metadata_phase=0;
        if(metadata_inputs!=68 || metadata_mixed_outputs!=12 || bursts<=before_bursts ||
           metadata_fast_queries==0 || metadata_slow_queries==0 || metadata_hit_miss_switches<2)
            $fatal(1,"ROWPIPE varying metadata hit/miss transition coverage or exact query/output count missing");
        $display("PASS ROWPIPE varying metadata hit-miss:12 queued queries, actual fast/slow switches, independent pixels/fractions/TAG order");

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
        $display("PASS SCATTER4 independent directed regression: INDEX7 WIDTH1920 HEIGHT1080 sparse queries, real FIFO2 wrapper,32 groups/128pixels, dual-write parity memories and non-vacuous pressure");

        if(cov_numeric_total<64 || cov_pre_hold==0 || cov_query_hold==0 || cov_pre_refill==0 ||
           cov_query_refill==0 || cov_pending_pre==0 || first_latency!=4 || stream_outputs!=64)
            $fatal(1,"ROWPIPE added-stage arithmetic/stall/refill/frame/latency coverage vacuous");
        summary=$fopen("rowpipe-main-summary.json","w");
        $fdisplay(summary,"{\"passed\":true,\"width\":1920,\"height\":1080,\"sparse_queries_only\":true,\"numeric_checks\":%0d,\"pre_hold\":%0d,\"query_hold\":%0d,\"pre_refill\":%0d,\"query_refill\":%0d,\"pending_pre\":%0d,\"first_valid_latency_cycles\":%0d,\"stream_outputs\":%0d,\"stream_span_cycles\":%0d,\"fault_cases\":4,\"ar_stall\":%0d,\"output_stall\":%0d,\"ram_checks\":%0d,\"reset_last_scatter\":%0d,",cov_numeric_total,cov_pre_hold,cov_query_hold,cov_pre_refill,cov_query_refill,cov_pending_pre,first_latency,stream_outputs,stream_last-stream_first,cov_ar_stall,cov_out_stall,cov_ram_verified,cov_last_reset);
        $fdisplay(summary,"\"metadata_inputs\":%0d,\"metadata_warm_outputs\":%0d,\"metadata_warm_span_cycles\":%0d,\"metadata_stalled_outputs\":%0d,\"metadata_all_field_changes\":%0d,\"metadata_input_stall\":%0d,\"metadata_output_hold\":%0d,\"metadata_pre_hold\":%0d,\"metadata_query_hold\":%0d,\"metadata_mixed_outputs\":%0d,\"metadata_fast_queries\":%0d,\"metadata_slow_queries\":%0d,\"metadata_hit_miss_switches\":%0d}",metadata_inputs,metadata_warm_outputs,metadata_warm_last-metadata_warm_first,metadata_stalled_outputs,metadata_all_field_changes,metadata_input_stall,metadata_output_hold,metadata_pre_hold,metadata_query_hold,metadata_mixed_outputs,metadata_fast_queries,metadata_slow_queries,metadata_hit_miss_switches);
        $fclose(summary);finished=1;
    end
    initial begin #8000000;$fatal(1,"SCATTER4 directed regression bounded timeout");end
endmodule

module rowpipe_generic639_exerciser(output reg finished=0);
    reg clk=0;always #4 clk=~clk;
    reg rst_n=0,frame_valid=0,in_valid=0;
    reg signed [23:0] in_x=0,in_y=0;reg [24:0] in_tag=0;
    wire frame_ready,in_ready,failed;wire [7:0] fault;
    ddr_compact_neighbour_cache_core_scatter4_rowpipe #(.WIDTH(639),.HEIGHT(480),.TAG_W(25),.TIMEOUT_BITS(16)) dut(
        .clk(clk),.rst_n(rst_n),.frame_valid(frame_valid),.frame_ready(frame_ready),.frame_base(28'd0),
        .in_valid(in_valid),.in_ready(in_ready),.in_x(in_x),.in_y(in_y),.in_tag(in_tag),
        .out_ready(1'b0),.arready(1'b0),.rdata(256'd0),.rvalid(1'b0),.rlast(1'b0),.rid(4'd0),.failed(failed),.fault(fault));
    integer checks=0,summary;
    task automatic arithmetic_case(input signed [23:0] x,y);
        longint signed xx,yy,number;
        begin
            @(negedge clk);rst_n=0;frame_valid=0;in_valid=0;
            repeat(4)@(negedge clk);rst_n=1;
            @(negedge clk);frame_valid=1;do @(posedge clk);while(!frame_ready);
            @(negedge clk);frame_valid=0;in_valid=1;in_x=x;in_y=y;in_tag=25'h1000123;
            do @(posedge clk);while(!in_ready);
            @(negedge clk);in_valid=0;wait(dut.query_valid);@(negedge clk);
            if(failed || dut.query_x!=={x[23],x[23:8]} || dut.query_y!=={y[23],y[23:8]} ||
               dut.query_fx!==x[7:0] || dut.query_fy!==y[7:0] || dut.query_tag!==25'h1000123)
                $fatal(1,"ROWPIPE generic639 metadata/handshake failed");
            for(integer n=0;n<4;n=n+1)begin
                xx=x;yy=y;xx=(xx>>>8)+(n%2);yy=(yy>>>8)+(n/2);number=yy*639+xx;
                if(dut.pixel_number[n]!==number[31:0] || dut.in_bounds[n]!=(xx>=0&&xx<639&&yy>=0&&yy<480))
                    $fatal(1,"ROWPIPE generic639 signed64 oracle differs n%0d",n);
            end
            checks=checks+1;
        end
    endtask
    initial begin
        arithmetic_case(-1,-1);arithmetic_case(0,0);arithmetic_case(638*256+255,479*256+255);
        arithmetic_case(639*256,480*256);arithmetic_case(24'sh7fffff,24'sh7fffff);
        arithmetic_case(-8388608,-8388608);
        if(checks!=6)$fatal(1,"ROWPIPE generic639 coverage missing");
        summary=$fopen("rowpipe-generic-summary.json","w");
        $fdisplay(summary,"{\"passed\":true,\"width\":639,\"signed64_arithmetic_cases\":6}");$fclose(summary);
        $display("PASS ROWPIPE generic639 independent signed64 six arithmetic cases");finished=1;
    end
    initial begin #1000000;$fatal(1,"ROWPIPE generic639 timeout");end
endmodule

module tb_rowpipe_cache;
    wire main_done,generic_done;
    rowpipe_cache_exerciser main_case(main_done);
    rowpipe_generic639_exerciser generic_case(generic_done);
    initial begin wait(main_done&&generic_done);
        $display("PASS ROWPIPE candidate unit: realRTL signed32 row pre-stage, independent64bit reference,1pixel throughput, backpressure/frame/reset/fault; no STA/hardware");$finish;end
    initial begin #8100000;$fatal(1,"ROWPIPE combined unit timeout");end
endmodule
