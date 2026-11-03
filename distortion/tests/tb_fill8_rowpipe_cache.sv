`timescale 1ns/1ps
// Independent sparse-query oracle. The identical test is executed against
// fill8 and frozen fill32; neither cache supplies the other's pixel oracle.
module fill8_cache_case #(parameter WIDTH=639,HEIGHT=480,INDEX_BITS=3)(output reg finished=0);
`ifdef FILL32_BASELINE
    localparam GROUPS=32;
`else
    localparam GROUPS=8;
`endif
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
`ifdef FILL32_BASELINE
    ddr_neighbour_cache_scatter4_rowpipe
`else
    ddr_neighbour_cache_scatter16_rowpipe
`endif
      #(.WIDTH(WIDTH),.HEIGHT(HEIGHT),.INDEX_BITS(INDEX_BITS),.TAG_W(25),.TIMEOUT_BITS(8)) dut(
        .clk(clk),.rst_n(rst_n),.frame_valid(frame_valid),.frame_ready(frame_ready),.frame_base(frame_base),
        .in_valid(in_valid),.in_ready(in_ready),.in_x(in_x),.in_y(in_y),.in_tag(in_tag),
        .out_valid(out_valid),.out_ready(out_ready),.p00(p00),.p10(p10),.p01(p01),.p11(p11),
        .fx(fx),.fy(fy),.out_tag(out_tag),.araddr(araddr),.arlen(arlen),.arvalid(arvalid),.arready(arready),
        .rdata(rdata),.rvalid(rvalid),.rlast(rlast),.rid(rid),.failed(failed),.fault(fault),
        .hits(hits),.misses(misses),.completed_queries(completed_queries));
    integer ticks=0,left=0,beat=0,burst_pixel=0,burst_epoch=0,burst_bank=0;
    integer active_epoch=0,active_bank=0,sent=0,received=0;
    integer mode=0,scatter_count=0,fill_count=0,ram_checks=0,normal_outputs=0;
    integer ar_stalls=0,r_gaps=0,out_stalls=0,in_stalls=0,queue_full=0,frame_pending=0;
    integer fast_queries=0,slow_queries=0,frame_drains=0,reset_last=0,fault_cases=0;
    integer total_bursts=0,scatter_cycles=0,scatter_start=-1,stream_first=-1,stream_last=-1;
    integer stream_accept=-1,stream_latency=-1,stream_outputs=0,warm_bursts=0;
    reg checking=1,force_ar_stall=0,force_output_stall=0,unthrottled=0,stream_phase=0;
    reg previous_scatter=0,held=0,held_ar=0;
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
        rvalid=rst_n&&left>0&&ticks%5!=0;
        rlast=left==1;rid=0;
        if(mode==1&&beat==3)rid=9;
        if(mode==2&&beat==3)rlast=1;
        if(mode==3&&left==1)rlast=0;
        if(mode==4&&left==0&&rst_n)begin rvalid=1;rlast=1;end
        if(mode==6)rvalid=0;
        for(integer n=0;n<16;n=n+1)rdata[n*16+:16]=source_word(burst_pixel+beat*16+n,burst_bank,burst_epoch);
        out_ready=rst_n&&!force_output_stall&&(unthrottled||ticks%11>=3);
    end
    always @(posedge clk)begin
        ticks=ticks+1;
        if(!rst_n)begin
            left<=0;beat<=0;sent<=0;received<=0;active_epoch<=0;active_bank<=0;
            held<=0;held_ar<=0;scatter_count=0;previous_scatter<=0;
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
                    sent<=sent+1;
                    if(stream_phase&&stream_accept<0)stream_accept=ticks;
                end
                if(out_valid&&!out_ready)out_stalls=out_stalls+1;
                if(out_valid&&out_ready)begin
                    if(received>=sent||{p00,p10,p01,p11,fx,fy,out_tag}!==expected[received])
                        $fatal(1,"independent pixel/metadata oracle WIDTH%0d output%0d tag%h got%h expected%h",WIDTH,received,out_tag,{p00,p10,p01,p11,fx,fy,out_tag},expected[received]);
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
                burst_bank<=active_bank;burst_epoch<=active_epoch;left<=8;beat<=0;total_bursts=total_bursts+1;
            end
            if(rvalid&&left>0)begin left<=left-1;beat<=beat+1;end
            if(dut.inner.scatter_write)begin
                if(!previous_scatter)begin scatter_count=0;scatter_start=ticks;end
                if(dut.inner.scatter_group!==scatter_count||dut.inner.valid_lines[dut.inner.selected_line]!==0)
                    $fatal(1,"scatter ordinal/early publication mismatch");
                if(dut.inner.read_enable||dut.inner.read_lower||left!=0||beat!=8)$fatal(1,"scatter overlaps read or incomplete DDR burst");
                scatter_count=scatter_count+1;scatter_cycles=scatter_cycles+1;
                if(scatter_count==GROUPS)begin
                    if(ticks-scatter_start!=GROUPS-1)$fatal(1,"scatter not consecutive");
                    #1;
                    if(dut.inner.valid_lines[dut.inner.selected_line]!==1||dut.inner.tags[dut.inner.selected_line]!==dut.inner.selected_block)
                        $fatal(1,"final scatter did not publish line");
                    // Verify all 128 independently generated source pixels,
                    // including lanes not touched by a later query.
                    for(integer p=0;p<128;p=p+1)begin
`ifdef FILL32_BASELINE
                        if(p%2==0)begin
                            if(dut.inner.even_pixels[dut.inner.selected_line*64+p/2]!==source_word(burst_pixel+p,burst_bank,burst_epoch))$fatal(1,"baseline even RAM mismatch");
                        end else if(dut.inner.odd_pixels[dut.inner.selected_line*64+p/2]!==source_word(burst_pixel+p,burst_bank,burst_epoch))$fatal(1,"baseline odd RAM mismatch");
`else
                        if(p%2==0)begin
                            if(dut.inner.even_pixels[dut.inner.selected_line*16+p/8][((p/2)%4)*16+:16]!==source_word(burst_pixel+p,burst_bank,burst_epoch))$fatal(1,"wide even RAM lane mismatch p%0d",p);
                        end else if(dut.inner.odd_pixels[dut.inner.selected_line*16+p/8][((p/2)%4)*16+:16]!==source_word(burst_pixel+p,burst_bank,burst_epoch))$fatal(1,"wide odd RAM lane mismatch p%0d",p);
`endif
                        ram_checks=ram_checks+1;
                    end
                    fill_count=fill_count+1;
                end
            end
            else if(previous_scatter&&scatter_count!=GROUPS)$fatal(1,"short/long scatter run");
            previous_scatter<=dut.inner.scatter_write;
            #1;
            if(stream_phase&&stream_accept>=0&&stream_latency<0&&out_valid)stream_latency=ticks-stream_accept;
        end
    end
    task automatic reset_case;
        begin
            @(negedge clk);rst_n=0;frame_valid=0;in_valid=0;mode=0;
            force_ar_stall=0;force_output_stall=0;unthrottled=0;checking=1;
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
        // Warm the exact lane-varying region, then prove latency and II=1.
        for(integer q=0;q<64;q=q+1)query(q+2,0,q*3,q*7,200+q);
        drain();before_bursts=total_bursts;unthrottled=1;stream_phase=1;
        @(negedge clk);in_valid=1;
        for(integer q=0;q<64;q=q+1)begin
            in_x=(q+2)*256+((q*41+3)&255);in_y=(q*67+13)&255;in_tag=25'h1001000+q;
            do @(posedge clk);while(!in_ready);
            @(negedge clk);
        end
        in_valid=0;drain();stream_phase=0;
        if(total_bursts!=before_bursts||stream_outputs!=64||stream_last-stream_first!=63||stream_latency!=4)
            $fatal(1,"warm throughput/latency mismatch fills%0d outputs%0d span%0d latency%0d",total_bursts-before_bursts,stream_outputs,stream_last-stream_first,stream_latency);
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
        // Reset exactly before the last scatter write. An incomplete block
        // must never publish or survive reset, even at the same base address.
        new_frame(0);query(127,1,1,2,500);
        wait(dut.inner.state==4&&dut.inner.scatter_group==GROUPS-1);
        @(negedge clk);rst_n=0;in_valid=0;frame_valid=0;reset_last=reset_last+1;
        repeat(4)@(negedge clk);rst_n=1;repeat(2)@(negedge clk);
        if(dut.inner.valid_lines!=0||out_valid)$fatal(1,"last-scatter reset leaked partial line/output");
        new_frame(0);query(127,1,3,4,501);drain();
        fault_case(1,8'h03);fault_case(2,8'h03);fault_case(3,8'h03);
        fault_case(4,8'h04);fault_case(5,8'h01);fault_case(6,8'h01);
        reset_case();new_frame(0);query(7,1,1,255,600);drain();
        if(fill_count<10||ram_checks!=fill_count*128||ar_stalls==0||r_gaps==0||out_stalls==0||in_stalls==0||
           queue_full==0||frame_pending==0||fast_queries==0||slow_queries==0||reset_last!=1||fault_cases!=6)
            $fatal(1,"mandatory coverage was vacuous");
        if(WIDTH==639)summary=$fopen("summary-639.json","w");else summary=$fopen("summary-1920.json","w");
        $fdisplay(summary,"{\"passed\":true,\"width\":%0d,\"height\":%0d,\"groups_per_fill\":%0d,\"complete_fills\":%0d,\"ram_pixels_checked\":%0d,\"normal_outputs\":%0d,\"ar_stalls\":%0d,\"r_gaps\":%0d,\"output_stalls\":%0d,\"input_stalls\":%0d,\"queue_full\":%0d,\"frame_pending\":%0d,\"fast_queries\":%0d,\"slow_queries\":%0d,\"frame_drains\":%0d,\"reset_before_last_scatter\":%0d,\"fault_cases\":%0d,\"warm_stream_outputs\":%0d,\"warm_span_cycles\":%0d,\"warm_first_valid_latency\":%0d}",
          WIDTH,HEIGHT,GROUPS,fill_count,ram_checks,normal_outputs,ar_stalls,r_gaps,out_stalls,in_stalls,queue_full,frame_pending,fast_queries,slow_queries,frame_drains,reset_last,fault_cases,stream_outputs,stream_last-stream_first,stream_latency);
        $fclose(summary);$display("PASS FILL8 independent WIDTH%0d groups%0d fills%0d outputs%0d faults%0d",WIDTH,GROUPS,fill_count,normal_outputs,fault_cases);finished=1;
    end
    initial begin #20000000;$fatal(1,"bounded cache case timeout WIDTH%0d",WIDTH);end
endmodule
module tb_fill8_rowpipe_cache;
    wire odd_done,native_done;
    fill8_cache_case odd_case(odd_done);
    fill8_cache_case #(.WIDTH(1920),.HEIGHT(1080),.INDEX_BITS(7)) native_case(native_done);
    initial begin wait(odd_done&&native_done);$display("PASS FILL8 complete independent cache regression; sparse queries, no PDS/hardware");$finish;end
endmodule
