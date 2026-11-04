`timescale 1ns/1ps
// Complete runtime public-wrapper bench. No lifetime oracle feeds the DUT.
// PROFILE0=small directed, PROFILE1=actual native Penn4096 coordinate slice.
// NEGATIVE1=unsolicited RVALID on final scatter edge; no broad error matrix.
module tb_capacity_lease;
    parameter PROFILE=2,NEGATIVE=0;
    parameter WIDTH=1920,HEIGHT=1080;
    parameter INDEX_BITS=6,QUERY_DEPTH=256;
    parameter LOOKAHEAD=QUERY_DEPTH;
    localparam TAG_W=24,MAXQ=6000,PIXELS=WIDTH*HEIGHT;
    localparam [27:0] BASE_A=28'h0100000,BASE_B=28'h0400000;
    reg clk=0;always #4 clk=~clk;
    reg rst_n=0,frame_valid=0,in_valid=0;
    reg [27:0] frame_base=BASE_A;
    reg signed [23:0] in_x=0,in_y=0;reg [23:0] in_tag=0;
    wire frame_ready,in_ready,out_valid,failed,arvalid;
    wire [23:0] p00,p10,p01,p11,out_tag;wire [7:0] fx,fy,fault;
    wire [27:0] araddr;wire [3:0] arlen;
    wire [31:0] hits,misses,completed_queries;
    wire arready,rvalid,rlast;wire [3:0] rid;wire [255:0] rdata;
    reg force_hold=0,periodic_bp=0,inject_r=0;
    wire out_ready=!force_hold && (!periodic_bp || ticks%13>=5);
    d256_runtime_prefetch_cache #(.WIDTH(WIDTH),.HEIGHT(HEIGHT),.INDEX_BITS(INDEX_BITS),
        .TAG_W(TAG_W),.QUERY_DEPTH(QUERY_DEPTH),.LOOKAHEAD(LOOKAHEAD),
        .IDLE_FLUSH_CYCLES(16),.TIMEOUT_BITS(10),.COMPACT_COORDS(1),
        .AREA_PROFILE(2),.CANDIDATE_KEY_PIPE(2),.HEAD_PREDECODE(1),.LOCAL_INFLIGHT_MASK(1)) dut(.*);

    function automatic [15:0] source_pixel(input integer absolute_pixel);
        reg [31:0] z;
        begin z=absolute_pixel*32'd109+32'h529b;
            z=z^(absolute_pixel>>3)^((absolute_pixel>>10)*32'h1f2d);source_pixel=z[15:0];end
    endfunction
    function automatic [23:0] expand_pixel(input [15:0] pixel);
        integer r,g,b;reg [7:0] r8,g8,b8;
        begin r=(pixel>>11)&31;g=(pixel>>5)&63;b=pixel&31;
            r8=(r<<3)|(r>>2);g8=(g<<2)|(g>>4);b8=(b<<3)|(b>>2);
            expand_pixel={r8,g8,b8};end
    endfunction
    function automatic [23:0] neighbour(input integer xq,yq,dx,dy,input [27:0] base);
        integer x,y;
        begin x=(xq>>>8)+dx;y=(yq>>>8)+dy;
            if(x<0 || x>=WIDTH || y<0 || y>=HEIGHT)neighbour=0;
            else neighbour=expand_pixel(source_pixel(base*2+y*WIDTH+x));end
    endfunction
    function automatic integer bounds_count(input integer xq,yq);
        integer x,y,k;
        begin x=xq>>>8;y=yq>>>8;bounds_count=0;
            for(k=0;k<4;k=k+1)if(x+k%2>=0 && x+k%2<WIDTH && y+k/2>=0 && y+k/2<HEIGHT)
                bounds_count=bounds_count+1;end
    endfunction
    function automatic [255:0] payload(input [27:0] addr,input integer beat);
        integer lane;
        begin for(lane=0;lane<16;lane=lane+1)
            payload[lane*16+:16]=source_pixel(addr*2+beat*16+lane);end
    endfunction

    integer ticks=0,sent=0,accepted=0,received=0,expected_bounds=0;
    integer checked_total=0,frame_accepts=0,reset_fill=0,reset_scatter=0;
    integer first_query_tick=0,last_result_tick=0;
    integer expected_x[0:MAXQ-1],expected_y[0:MAXQ-1];
    reg [23:0] expected_tag[0:MAXQ-1];reg [27:0] expected_base[0:MAXQ-1];
    reg [27:0] active_base=BASE_A;
    integer ar_count=0,read_beats=0,normal_fills=0,scatter_edges=0,fill_edges=0;
    integer input_stalls=0,output_stalls=0,ar_hold_edges=0,zero_r0=0;
    integer overlap_reads=0,lease_checks=0,publish_joins=0,generation_wait=0,demand_wait=0;
    integer frame_origin=0,independent_lease_checks=0,independent_live_queries=0;
    integer lease_qid,lease_global,lease_n,lease_x,lease_y,lease_block;
    integer fifo_full_edges=0,fifo_wp_wraps=0,fifo_rp_wraps=0,max_fifo_total=0;
    integer fill_accept_tick=0,max_fill_service_edges=0,frame_wait_edges=0;
    reg held_ar=0,held_out=0,held_input=0;
    reg [31:0] saved_ar;reg [135:0] saved_out;reg [71:0] saved_input;
    wire [135:0] output_tuple={out_tag,fx,fy,p00,p10,p01,p11};
    wire [71:0] input_tuple={in_tag,in_x,in_y};

    // Coordinated reset flushes the model and DUT together. No AR epoch field
    // exists, so this bench cannot prove arbitrary late RID0 beat separation.
    reg ddr_active=0;reg [27:0] response_addr=0;integer response_beat=0,ar_age=0;
    assign arready=!ddr_active && ar_age>=3;
    wire first_r=!ddr_active && arvalid && arready;
    assign rvalid=inject_r || (ddr_active ? ticks%5!=2:first_r);
    assign rlast=ddr_active && response_beat==7;
    assign rid=0;
    assign rdata=payload(ddr_active ? response_addr:araddr,ddr_active ? response_beat:0);
    always @(posedge clk)begin
        if(!rst_n)begin ddr_active<=0;response_addr<=0;response_beat<=0;ar_age<=0;end
        else begin
            if(arvalid && !arready)ar_age<=ar_age+1;
            else if(!arvalid || arready)ar_age<=0;
            if(arvalid && arready)begin
                if(ddr_active || arlen!==7 || araddr<active_base ||
                    araddr>=active_base+PIXELS/2 || (araddr-active_base)%64!=0)
                    $fatal(1,"DDR AR alignment/bounds/one-outstanding");
                if(!rvalid || rlast)$fatal(1,"missing zero-latency first R beat");
                response_addr<=araddr;response_beat<=1;ddr_active<=1;
            end else if(ddr_active && rvalid)begin
                if(response_beat==7)begin response_beat<=0;ddr_active<=0;end
                else response_beat<=response_beat+1;
            end
        end
    end

    always @(posedge clk)begin
        ticks<=ticks+1;
        if(ticks>300000)$fatal(1,"bounded runtime watchdog profile=%0d accepted=%0d received=%0d pending=%h",PROFILE,accepted,received,dut.pending_valid);
        if(!rst_n)begin
            accepted=0;received=0;expected_bounds=0;active_base=BASE_A;frame_origin=0;
            ar_count=0;read_beats=0;normal_fills=0;scatter_edges=0;fill_edges=0;
            held_ar=0;held_out=0;held_input=0;
            first_query_tick=0;last_result_tick=0;
        end else begin
            if(held_ar && (!arvalid || {arlen,araddr}!==saved_ar))$fatal(1,"AR changed under hold");
            if(held_out && !failed && (!out_valid || output_tuple!==saved_out))$fatal(1,"output changed under hold");
            if(held_input && !failed && (!in_valid || input_tuple!==saved_input))$fatal(1,"driver changed unaccepted input");
            held_ar=arvalid && !arready;saved_ar={arlen,araddr};
            held_out=out_valid && !out_ready;saved_out=output_tuple;
            held_input=in_valid && !in_ready;saved_input=input_tuple;
            if(held_ar)ar_hold_edges=ar_hold_edges+1;
            if(in_valid && !in_ready)input_stalls=input_stalls+1;
            if(out_valid && !out_ready)output_stalls=output_stalls+1;
            if(frame_valid && !frame_ready)frame_wait_edges=frame_wait_edges+1;
            if(frame_valid && frame_ready)begin
                active_base=frame_base;frame_accepts=frame_accepts+1;frame_origin=accepted;
            end
            if(in_valid && in_ready)begin
                if(accepted>=MAXQ)$fatal(1,"scoreboard capacity");
                if(accepted==0)first_query_tick=ticks;
                expected_x[accepted]=$signed(in_x);expected_y[accepted]=$signed(in_y);
                expected_tag[accepted]=in_tag;expected_base[accepted]=active_base;
                expected_bounds=expected_bounds+bounds_count($signed(in_x),$signed(in_y));
                accepted=accepted+1;
            end
            if(out_valid && out_ready)begin
                if(received>=accepted || out_tag!==expected_tag[received] ||
                    p00!==neighbour(expected_x[received],expected_y[received],0,0,expected_base[received]) ||
                    p10!==neighbour(expected_x[received],expected_y[received],1,0,expected_base[received]) ||
                    p01!==neighbour(expected_x[received],expected_y[received],0,1,expected_base[received]) ||
                    p11!==neighbour(expected_x[received],expected_y[received],1,1,expected_base[received]) ||
                    fx!==expected_x[received][7:0] || fy!==expected_y[received][7:0])
                    $fatal(1,"pixel/frac/tag oracle query=%0d tag=%0d expected_tag=%0d xy=%0d,%0d",received,out_tag,expected_tag[received],expected_x[received],expected_y[received]);
                received=received+1;checked_total=checked_total+1;last_result_tick=ticks;
            end
            if(arvalid && arready)begin ar_count=ar_count+1;zero_r0=zero_r0+1;end
            if(rvalid && (ddr_active || first_r))read_beats=read_beats+1;
            if(dut.fill_accept)begin
                if(dut.active_valid[dut.job_line] && dut.active_refs[dut.job_line]!=0)
                    $fatal(1,"fill accepted without victim active-ref lease");
                // Independent raw-coordinate audit of already scouted, not yet
                // retired queries. Future unscouted A/B/A tokens do not own the
                // old generation. Counts select the frontier; DUT refs and line
                // decode are not used to reconstruct a query's source blocks.
                if(dut.active_valid[dut.job_line])begin
                    independent_lease_checks=independent_lease_checks+1;
                    if(dut.admitted_count<dut.retired_count ||
                        dut.admitted_count-dut.retired_count>QUERY_DEPTH+6)
                        $fatal(1,"independent lease frontier exceeds bounded live window");
                    for(lease_qid=dut.retired_count;lease_qid<dut.admitted_count;lease_qid=lease_qid+1)begin
                        lease_global=frame_origin+lease_qid;
                        if(lease_global<0 || lease_global>=accepted)
                            $fatal(1,"scouted query missing from independent input scoreboard");
                        independent_live_queries=independent_live_queries+1;
                        for(lease_n=0;lease_n<4;lease_n=lease_n+1)begin
                            lease_x=(expected_x[lease_global]>>>8)+(lease_n%2);
                            lease_y=(expected_y[lease_global]>>>8)+(lease_n/2);
                            if(lease_x>=0 && lease_x<WIDTH && lease_y>=0 && lease_y<HEIGHT)begin
                                lease_block=(lease_y*WIDTH+lease_x)/128;
                                if(lease_block==dut.active_tag[dut.job_line])
                                    $fatal(1,"independent victim still referenced qid=%0d global=%0d block=%0d",lease_qid,lease_global,lease_block);
                            end
                        end
                    end
                end
                lease_checks=lease_checks+1;fill_edges=0;fill_accept_tick=ticks;
            end
            if(dut.store.scatter_write)begin
                fill_edges=fill_edges+1;scatter_edges=scatter_edges+1;
                if(dut.store.read_fire)overlap_reads=overlap_reads+1;
            end
            if(dut.fill_done_good)begin
                if(fill_edges!=32)$fatal(1,"normal fill scatter count %0d",fill_edges);
                normal_fills=normal_fills+1;
                if(ticks-fill_accept_tick>max_fill_service_edges)max_fill_service_edges=ticks-fill_accept_tick;
            end
            if(dut.scout_commit && dut.fill_done_good && dut.add_pending[dut.inflight_line])
                publish_joins=publish_joins+1;
            if(dut.generation_blocked)generation_wait=generation_wait+1;
            if(dut.demand_blocked)demand_wait=demand_wait+1;
            if(dut.query_fifo.total==QUERY_DEPTH)fifo_full_edges=fifo_full_edges+1;
            if(dut.query_fifo.total>max_fifo_total)max_fifo_total=dut.query_fifo.total;
            // Count real last-address pointer advances, never frame/reset clears.
            if(!dut.accept_frame && !failed)begin
                if(dut.query_fifo.push && dut.query_fifo.wp==QUERY_DEPTH-1)
                    fifo_wp_wraps=fifo_wp_wraps+1;
                if(dut.query_fifo.fetch && dut.query_fifo.rp==QUERY_DEPTH-1)
                    fifo_rp_wraps=fifo_rp_wraps+1;
            end
            if(failed && out_valid)$fatal(1,"faulted wrapper published output");
            if(failed && NEGATIVE==0)$fatal(1,"unexpected runtime fault=%h",fault);
        end
    end

    task automatic frame(input [27:0] base,input integer must_wait);
        begin
            @(negedge clk);frame_base=base;frame_valid=1;
            if(must_wait && frame_ready)$fatal(1,"frame did not wait for old output");
            @(posedge clk);while(!frame_ready)@(posedge clk);
            @(negedge clk);frame_valid=0;
        end
    endtask
    task automatic query(input integer xq,yq);
        begin
            @(negedge clk);in_valid=1;in_x=xq;in_y=yq;in_tag=24'h560000+sent;
            @(posedge clk);while(!in_ready)@(posedge clk);
            sent=sent+1;@(negedge clk);in_valid=0;
        end
    endtask
    // mode0=A, mode1=A/A/B/B/A same-index sequence, mode2=A prefix then C.
    // A=(x2,y0), B=(x2,y4), C=(x130,y2): native small mapping is real RTL.
    task automatic stream(input integer length,mode);
        integer q,sel;
        begin
            @(negedge clk);
            for(q=0;q<length;q=q+1)begin
                sel=mode==1 ? ((q>=16 && q<32) ? 1:0):mode==2 && q==24 ? 2:0;
                in_x=(sel==2 ? 130:2)*256+((q*13)&255);
                in_y=(sel==1 ? 4:sel==2 ? 2:0)*256+((q*17)&255);
                in_tag=24'h560000+sent;in_valid=1;
                @(posedge clk);while(!in_ready)@(posedge clk);
                sent=sent+1;@(negedge clk);
            end
            in_valid=0;
        end
    endtask
    task automatic drained;
        begin
            @(posedge clk);while(received!=accepted || !frame_ready)@(posedge clk);
            @(negedge clk);
        end
    endtask
    task automatic conservation;
        begin
            drained;
            if(completed_queries!==received || received!=accepted ||
                hits+misses!==expected_bounds || misses!==ar_count || normal_fills!=ar_count ||
                read_beats!=8*ar_count || scatter_edges!=32*normal_fills || ddr_active)
                $fatal(1,"counter/DDR conservation q=%0d complete=%0d h=%0d m=%0d bounds=%0d ar=%0d fills=%0d",received,completed_queries,hits,misses,expected_bounds,ar_count,normal_fills);
        end
    endtask
    task automatic coordinated_reset;
        begin
            @(negedge clk);rst_n=0;in_valid=0;frame_valid=0;force_hold=0;inject_r=0;
            repeat(3)@(posedge clk);
            @(negedge clk);sent=0;rst_n=1;
            @(posedge clk);#1;
            if(failed || in_ready || hits!=0 || misses!=0 || completed_queries!=0 || arvalid || ddr_active)
                $fatal(1,"coordinated reset did not clear cache/DDR");
        end
    endtask
    reg [47:0] penn[0:4095];string penn_path;
    integer i,before_misses,before_joins,before_overlap,before_generations,before_ar;
    reg [31:0] prior_epoch;
    initial begin
        repeat(4)@(posedge clk);@(negedge clk);rst_n=1;frame(BASE_A,0);
        if(NEGATIVE==1)begin
            query(2*256+5,-256+7);
            @(negedge clk);while(!(dut.store.state==3 && dut.store.scatter_word==31))@(negedge clk);
            inject_r=1;@(posedge clk);#1;
            if(!failed || fault!==8'h04 || out_valid || dut.store.fill_done || dut.fill_done_good)
                $fatal(1,"final scatter fault lost priority");
            @(negedge clk);inject_r=0;
            repeat(5)begin @(posedge clk);#1;
                if(!failed || fault!==8'h04 || in_ready || frame_ready || out_valid)
                    $fatal(1,"runtime fault not quarantined");
            end
            // Logical quarantine only; physical RAM/store payload need not erase.
            if(dut.active_valid!==0 || dut.pending_valid!==0 || dut.skid_count!==0 ||
                dut.decoded_valid!==1'b0 || dut.head_valid!==1'b0 || dut.query_fifo.empty!==1'b1)
                $fatal(1,"fault cleanup left logical directory/queue state live");
            $display("METRICS profile=%0d negative=1 fault=%0d lease_checks=%0d",PROFILE,fault,lease_checks);
            $display("PASS_D256_RUNTIME negative=1");$finish;
        end
        if(PROFILE==1)begin
            penn_path="tests/penn_slice4096.mem";
            if($value$plusargs("PENN_MEM=%s",penn_path))begin end
            $readmemh(penn_path,penn);
            periodic_bp=1;
            @(negedge clk);
            for(i=0;i<4096;i=i+1)begin
                in_valid=1;in_x=$signed(penn[i][47:24]);in_y=$signed(penn[i][23:0]);
                in_tag=24'h560000+sent;
                @(posedge clk);while(!in_ready)@(posedge clk);
                sent=sent+1;@(negedge clk);
            end
            in_valid=0;conservation;
            if(hits!==3997 || misses!==13 || completed_queries!==4096 || expected_bounds!=4010)
                $fatal(1,"Penn runtime logical counters differ h=%0d m=%0d c=%0d bounds=%0d",hits,misses,completed_queries,expected_bounds);
        end else if(PROFILE==2)begin
            if(WIDTH!=1920 || HEIGHT!=1080 || INDEX_BITS!=6 || QUERY_DEPTH!=256)
                $fatal(1,"capacity lease fixture requires native INDEX6 Q256");
            // Two physical rows/query. A=(block0,15), B=(block62,77).
            // Both pairs map to lines0/32 at INDEX6. Keep old A in the output
            // pipeline so its live lease prevents the pending B overwrite.
            force_hold=1;query(2*256+37,53);
            @(negedge clk);while(!out_valid)@(negedge clk);
            before_ar=ar_count;before_generations=generation_wait;
            query(258*256+71,4*256+19);
            query(2*256+101,89);
            @(negedge clk);while(!dut.generation_blocked)@(negedge clk);
            repeat(8)begin
                @(negedge clk);
                if(!dut.active_valid[0] || dut.active_tag[0]!=0 ||
                   dut.active_refs[0]==0 || !dut.pending_valid[0] ||
                   dut.pending_tag[0]!=62 || !dut.generation_blocked ||
                   dut.decoded_block[0]!=0 || ar_count!=before_ar || dut.fill_accept)
                    $fatal(1,"third-generation A escaped live A/pending B lease");
            end
            force_hold=0;conservation;
            if(received!=3 || misses!=6 || hits!=6 || generation_wait<=before_generations ||
               independent_lease_checks==0 || independent_live_queries==0)
                $fatal(1,"native INDEX6 A/B/A tuple/lease/counter coverage missing");
            $display("CAPACITY_LEASE index_bits=6 queries=3 misses=%0d hits=%0d third_generation_hold_edges=8 generation_stalls=%0d independent_lease_checks=%0d independent_live_queries=%0d",misses,hits,generation_wait,independent_lease_checks,independent_live_queries);
            // Cold next epoch uses a distinct real DDR base. No old tag/lease
            // may authorize a prior payload; the existing oracle includes base.
            prior_epoch=dut.epoch;before_misses=misses;
            frame(BASE_B,0);query(2*256+23,31);conservation;
            if(dut.epoch!==prior_epoch+1 || misses-before_misses!=2)
                $fatal(1,"capacity new-base epoch did not refill cold rows");
            // A single coordinated FILL reset checks the resized flags and
            // directory clear; it does not claim arbitrary late DDR-beat safety.
            frame(BASE_A,0);query(2*256+47,17);
            @(negedge clk);while(dut.store.state!=2)@(negedge clk);
            coordinated_reset;reset_fill=reset_fill+1;
            frame(BASE_B,0);query(2*256+79,61);conservation;
            if(dut.local_inflight_owned!==0 || reset_fill!=1)
                $fatal(1,"capacity coordinated-reset owner not drained");
        end else begin
            if(WIDTH!=256 || HEIGHT!=8 || INDEX_BITS!=3 || QUERY_DEPTH!=32)
                $fatal(1,"directed small fixture parameter mismatch");
            // Non-full FIFO targeted join at the publication edge. Push word30,
            // decode word31, scout commit while the store publishes fill_done.
            before_joins=publish_joins;query(2*256+5,-256+7);
            @(negedge clk);while(!(dut.store.state==3 && dut.store.scatter_word==30))@(negedge clk);
            in_valid=1;in_x=2*256+211;in_y=-256+93;in_tag=24'h560000+sent;
            @(posedge clk);if(!in_ready)$fatal(1,"target join input not ready");
            sent=sent+1;@(negedge clk);in_valid=0;conservation;
            if(publish_joins<=before_joins || misses!=1 || hits!=3)$fatal(1,"join/publication coverage/counters");
            // Fresh epoch, cold identical queries: one pending fill per row,
            // even with many queued joins. Hold the sink until FIFO really full.
            frame(BASE_B,0);before_misses=misses;force_hold=1;
            fork
                stream(96,0);
                begin
                    @(negedge clk);while(dut.query_fifo.total!=QUERY_DEPTH)@(negedge clk);
                    repeat(6)@(negedge clk);force_hold=0;
                end
            join
            conservation;
            if(misses!=before_misses+2 || fifo_full_edges==0 || fifo_wp_wraps==0 || fifo_rp_wraps==0)
                $fatal(1,"pending join/full FIFO/wrap coverage");
            before_misses=misses;before_generations=generation_wait;periodic_bp=1;
            stream(40,1);conservation;
            if(misses!=before_misses+4 || generation_wait<=before_generations)
                $fatal(1,"A/A/B/B/A generation progress/counters");
            // A is warm. C is independent. Keeping24 A queries before C allows
            // resident reads to overlap the first C scatter after sink release.
            periodic_bp=0;force_hold=1;before_overlap=overlap_reads;before_misses=misses;
            fork
                stream(96,2);
                begin
                    @(negedge clk);
                    while(!(dut.store.state==3 && dut.store.selected_block==5))@(negedge clk);
                    force_hold=0;
                end
            join
            conservation;
            if(overlap_reads-before_overlap<16 || misses!=before_misses+2)
                $fatal(1,"nonconflicting background read/fill overlap reads=%0d",overlap_reads-before_overlap);
            periodic_bp=1;
            for(i=0;i<4;i=i+1)begin
                query(i*256+91,77);query((124+i)*256+213,256+19);
                query((252+i)*256+5,117);
            end
            query(-256+231,65);query(WIDTH*256+77,113);query(13*256+55,-256+5);
            query(0,7*256+117);query(127*256+49,7*256+255);
            query(255*256+201,7*256+63);query(17*256,HEIGHT*256+33);conservation;
            // Frame request is pending while an old output is backpressured.
            force_hold=1;query(2*256+33,91);
            fork
                frame(BASE_A,1);
                begin
                    @(negedge clk);while(!frame_valid)@(negedge clk);
                    repeat(5)begin @(negedge clk);if(frame_ready || in_ready)$fatal(1,"frame drain bypass");end
                    force_hold=0;
                end
            join
            before_misses=misses;query(2*256+137,91);conservation;
            if(misses!=before_misses+2 || frame_wait_edges<5)$fatal(1,"frame epoch did not invalidate");
            // Reset while response and scatter are active; DDR model flushes
            // synchronously with the core. All pre-reset queued queries cancel.
            frame(BASE_B,0);query(2*256,0);
            @(negedge clk);while(dut.store.state!=2)@(negedge clk);
            coordinated_reset;reset_fill=reset_fill+1;
            frame(BASE_A,0);query(2*256+73,17);conservation;
            frame(BASE_B,0);query(2*256,0);
            @(negedge clk);while(!(dut.store.state==3 && dut.store.scatter_word==10))@(negedge clk);
            coordinated_reset;reset_scatter=reset_scatter+1;
            frame(BASE_B,0);stream(48,0);conservation;
            if(reset_fill!=1 || reset_scatter!=1 || publish_joins==0 ||
                input_stalls==0 || output_stalls==0 || lease_checks==0)
                $fatal(1,"small coverage incomplete");
        end
        $display("METRICS profile=%0d queries=%0d checked_total=%0d hits=%0d misses=%0d bounds=%0d fills=%0d scatter_edges=%0d query_reads_during_scatter=%0d lease_checks=%0d independent_lease_checks=%0d independent_live_queries=%0d publish_joins=%0d fifo_full_edges=%0d fifo_wp_wraps=%0d fifo_rp_wraps=%0d max_fifo_total=%0d generation_stalls=%0d demand_stalls=%0d input_stalls=%0d output_stalls=%0d ar_hold_edges=%0d zero_r0=%0d max_fill_service_edges=%0d frame_wait_edges=%0d reset_fill=%0d reset_scatter=%0d service_edge_distance=%0d",PROFILE,received,checked_total,hits,misses,expected_bounds,normal_fills,scatter_edges,overlap_reads,lease_checks,independent_lease_checks,independent_live_queries,publish_joins,fifo_full_edges,fifo_wp_wraps,fifo_rp_wraps,max_fifo_total,generation_wait,demand_wait,input_stalls,output_stalls,ar_hold_edges,zero_r0,max_fill_service_edges,frame_wait_edges,reset_fill,reset_scatter,last_result_tick-first_query_tick);
        $display("PASS_CAPACITY_LEASE profile=%0d",PROFILE);$finish;
    end
endmodule
