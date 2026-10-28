`timescale 1ps/1ps
// One consumer and a REAL unchanged synchronous-read dual-clock FIFO.
// Small raster only: these tests do not establish native timing or HDMI PHY.
module tb_board1080_scan;
    localparam W=32,H=16,N=W*H,BEATS=N/16,HT=80,VT=40,X0=10,Y0=3;
    reg clk=0,wr_clk=0;always #4000 wr_clk=~wr_clk;
    integer phase=0,half_ps;
    initial forever begin phase=phase+2000000;half_ps=phase/297;phase=phase%297;#(half_ps)clk=~clk;end
    reg rst_n=0,enable=1,abort=0;reg [7:0] abort_fault=0;
    wire request_toggle;wire [31:0] request_epoch;
    reg grant_toggle=0,grant_valid=0;reg [31:0] grant_epoch=0,grant_checksum=0,grant_id=0;
    reg grant_bank=0;wire grant_ack_toggle;reg done_ack_toggle=0;
    wire fifo_rd_en,fifo_ready,fifo_valid;wire [255:0] fifo_data;
    wire hs,vs,de,display_valid,done_toggle,done_good,done_bank;
    wire [7:0] r,g,b,fault;wire [31:0] done_epoch,done_id,done_crc,consumed_pixels;
    wire frame_active,active_bank,frame_start,frame_last,pixel_valid,failed,draining;
    wire [31:0] active_id,completed_frames,underflows,mismatches;
    ddr_video_output_1080_board #(.WIDTH(W),.HEIGHT(H),.HT(HT),.VT(VT),.HS(4),.VS(1),
        .X0(X0),.Y0(Y0),.AW(W),.AH(H)) dut(
        .clk(clk),.rst_n(rst_n),.enable(enable),.abort(abort),.abort_fault(abort_fault),
        .request_toggle(request_toggle),.request_epoch(request_epoch),.grant_toggle(grant_toggle),
        .grant_valid(grant_valid),.grant_epoch(grant_epoch),.grant_checksum(grant_checksum),
        .grant_id(grant_id),.grant_bank(grant_bank),.grant_ack_toggle(grant_ack_toggle),
        .done_ack_toggle(done_ack_toggle),.fifo_ready(fifo_ready),.fifo_valid(fifo_valid),
        .fifo_data(fifo_data),.fifo_rd_en(fifo_rd_en),.hs(hs),.vs(vs),.de(de),.r(r),.g(g),.b(b),
        .display_valid(display_valid),.done_toggle(done_toggle),.done_good(done_good),.done_epoch(done_epoch),
        .done_id(done_id),.done_bank(done_bank),.done_crc(done_crc),.consumed_pixels(consumed_pixels),
        .frame_active(frame_active),.active_id(active_id),.active_bank(active_bank),
        .frame_start(frame_start),.frame_last(frame_last),.pixel_valid(pixel_valid),
        .failed(failed),.fault(fault),.draining(draining),
        .completed_frames(completed_frames),.underflows(underflows),.mismatches(mismatches));
    reg wr_en=0;reg [255:0] wr_data=0;
    wire wr_full,wr_ready,rd_empty,rd_ready,rd_valid;wire [255:0] rd_data;
    wire [6:0] rd_available,wr_used;
    video_async_fifo #(.DATA_BITS(256),.ADDR_BITS(6)) fifo(
        .wr_clk(wr_clk),.rd_clk(clk),.rst_n(rst_n),.wr_en(wr_en),.wr_data(wr_data),
        .wr_full(wr_full),.wr_ready(wr_ready),.rd_en(fifo_rd_en),.rd_data(rd_data),.rd_valid(rd_valid),
        .rd_empty(rd_empty),.rd_ready(rd_ready),.rd_available(rd_available),.wr_used(wr_used));
    integer cycles=0;
    wire read_gate=cycles%7>=2;
    reg force_ready_open=0;
    reg rogue_valid=0;reg [255:0] rogue_data=0;
    assign fifo_ready=rd_ready && (read_gate || force_ready_open);
    assign fifo_valid=rd_valid || rogue_valid;
    assign fifo_data=rogue_valid ? rogue_data:rd_data;
    function automatic [15:0] pattern(input integer index,input integer version);
        begin pattern=16'h5a3c^(index*73)^(index>>3)^(version*16'h1357);end
    endfunction
    function automatic [255:0] beat(input integer offset,input integer version);
        integer j;begin for(j=0;j<16;j=j+1)beat[j*16+:16]=pattern(offset*16+j,version);end
    endfunction
    function automatic [31:0] crc_byte(input [31:0] previous,input [7:0] value);
        reg [31:0] c;integer j;
        begin c=previous^value;for(j=0;j<8;j=j+1)c=c[0] ? (c>>1)^32'hedb88320:c>>1;crc_byte=c;end
    endfunction
    function automatic [31:0] crc_pixels(input integer version,input integer count);
        reg [31:0] c;reg [15:0] p;integer j;
        begin c=32'hffffffff;for(j=0;j<count;j=j+1)begin
            p=pattern(j,version);c=crc_byte(crc_byte(c,p[7:0]),p[15:8]);
        end crc_pixels=~c;end
    endfunction
    function automatic [23:0] expand565(input [15:0] p);
        expand565={p[15:11],p[15:13],p[10:5],p[10:9],p[4:0],p[4:2]};
    endfunction
    reg request_seen=0,previous_read=0,previous_done=0;
    reg saved_done_before=0;
    integer expected_version=0,expected_id=0,expected_bank=0,case_pixels=0,case_starts=0,case_lasts=0;
    integer good_events=0,bad_events=0,requests=0,returns=0,ready_stalls=0,return_latency_events=0;
    integer fault_cases=0,cases=0,idx,old_x,old_y;
    reg [31:0] expected_epoch=0;reg [130:0] held_done;
    reg expected_de,expected_hs,expected_vs;
    always @(posedge clk)begin
        cycles=cycles+1;
        if(cycles>2000000)$fatal(1,"scan test exceeded2M pixel cycles");
        if(!rst_n || !dut.reset_sync[1])begin previous_read=0;previous_done=0;end
        else begin
            if(rd_valid!==previous_read)$fatal(1,"real FIFO return did not have exactly one read-clock latency");
            previous_read=fifo_rd_en;
            if(fifo_rd_en)requests=requests+1;
            if(rd_valid)begin returns=returns+1;return_latency_events=return_latency_events+1;end
            if(frame_active && !fifo_ready)ready_stalls=ready_stalls+1;
            old_x=dut.x;old_y=dut.y;
            expected_de=old_x>=X0&&old_x<X0+W&&old_y>=Y0&&old_y<Y0+H;
            expected_hs=old_x<4;expected_vs=old_y<1;
            #1;
            if(de!==expected_de || hs!==expected_hs || vs!==expected_vs)$fatal(1,"registered raster control mismatch");
            if(pixel_valid)begin
                idx=(old_y-Y0)*W+old_x-X0;
                if(!expected_de || idx!=case_pixels || {r,g,b}!==expand565(pattern(idx,expected_version)))
                    $fatal(1,"independent pixel/order RGB565 oracle differs idx=%0d expected=%0d",idx,case_pixels);
                if(frame_start!==(case_pixels==0))$fatal(1,"frame_start not aligned with first output pixel");
                case_pixels=case_pixels+1;if(frame_start)case_starts=case_starts+1;
                if(frame_last)begin if(case_pixels!=N)$fatal(1,"early last pixel");case_lasts=case_lasts+1;end
            end else if({r,g,b}!==24'd0 || frame_start || frame_last)$fatal(1,"black/fault/blank output emitted a pixel");
            if(frame_active && (active_id!=expected_id || active_bank!=expected_bank))$fatal(1,"accepted lease identity changed with input bundle");
            if(done_toggle!=previous_done)begin
                if(done_good)begin
                    if(failed || done_id!=expected_id || done_bank!=expected_bank || done_epoch!=expected_epoch ||
                        done_crc!==crc_pixels(expected_version,N) || consumed_pixels!=N || case_pixels!=N ||
                        case_starts!=1 || case_lasts!=1 || !display_valid)
                        $fatal(1,"good event without exact frame/CRC/identity/health");
                    good_events=good_events+1;
                end else bad_events=bad_events+1;
                previous_done=done_toggle;
            end
            if(failed && (display_valid || frame_active || pixel_valid || {r,g,b}!=0 || !draining))
                $fatal(1,"fault did not immediately revoke health/output and enter drain");
        end
    end
    task automatic common_reset;
        begin
            @(negedge clk);rst_n=0;enable=1;abort=0;abort_fault=0;wr_en=0;rogue_valid=0;force_ready_open=0;
            grant_toggle=0;grant_valid=0;grant_epoch=0;grant_checksum=0;grant_id=0;grant_bank=0;done_ack_toggle=0;
            request_seen=0;case_pixels=0;case_starts=0;case_lasts=0;
            repeat(8)@(negedge clk);rst_n=1;repeat(4)@(negedge clk);
            if(failed || draining || display_valid || frame_active || done_toggle || done_good || !rd_empty)
                $fatal(1,"common reset did not clear stale lease/FIFO/failure");
        end
    endtask
    task automatic next_request;
        begin
            do @(negedge clk);while(request_toggle==request_seen);
            request_seen=request_toggle;expected_epoch=request_epoch;
            if(failed || request_epoch==0)$fatal(1,"request missing valid epoch/health");
        end
    endtask
    task automatic load_words(input integer version,input integer first,input integer count);
        integer j;
        begin
            for(j=0;j<count;j=j+1)begin
                @(negedge wr_clk);while(!wr_ready)@(negedge wr_clk);
                wr_data=beat(first+j,version);wr_en=1;
                @(posedge wr_clk);@(negedge wr_clk);wr_en=0;
                if(j%3==0)@(negedge wr_clk);
            end
        end
    endtask
    task automatic descriptor(input integer valid_frame,input integer id,input integer bank,input integer version,
        input integer words_count,input integer bad_crc,input integer stale_epoch);
        begin
            next_request();case_pixels=0;case_starts=0;case_lasts=0;
            expected_version=version;expected_id=id;expected_bank=bank;saved_done_before=done_toggle;
            if(words_count!=0)load_words(version,0,words_count);
            grant_valid=valid_frame;grant_epoch=expected_epoch-stale_epoch;
            grant_id=id;grant_bank=bank;grant_checksum=crc_pixels(version,N)^(bad_crc ? 32'h1:32'h0);
            repeat(2)@(negedge clk);grant_toggle=!grant_toggle;
            do @(negedge clk);while(grant_ack_toggle!=grant_toggle);
            // After ACK the producer is free to reuse its bus. The local lease
            // must retain accepted ID/bank/CRC/epoch through every FIFO stall.
            grant_id=32'hdeadbeef;grant_checksum=0;grant_bank=!bank;grant_epoch=0;
        end
    endtask
    task automatic good_done;
        begin
            wait(done_toggle!=saved_done_before);@(negedge clk);
            if(!done_good || failed || consumed_pixels!=N || done_crc!==crc_pixels(expected_version,N))
                $fatal(1,"expected good frame did not complete");
        end
    endtask
    task automatic ack_done;
        begin @(negedge clk);done_ack_toggle=done_toggle;repeat(4)@(negedge clk);end
    endtask
    task automatic quarantine(input [7:0] expected_fault,input integer allow_held_good);
        reg old_request;integer j;
        begin
            wait(failed);@(negedge clk);old_request=request_toggle;
            if(fault!==expected_fault || !draining || display_valid || frame_active || (!allow_held_good&&done_good))
                $fatal(1,"wrong fail-closed fault got=%h expected=%h",fault,expected_fault);
            for(j=0;j<HT*VT+10;j=j+1)begin
                @(negedge clk);
                if(!failed || fault!==expected_fault || request_toggle!=old_request || pixel_valid || {r,g,b}!=0)
                    $fatal(1,"fault/request/black quarantine was not sticky");
            end
            fault_cases=fault_cases+1;
        end
    endtask
    initial begin
        // Healthy new ID, legal repeated front, then a new ID/bank. Keep the
        // latest good result unacknowledged across two frame boundaries.
        common_reset();descriptor(1,1,0,0,BEATS,0,0);good_done();ack_done();
        descriptor(1,1,0,0,BEATS,0,0);good_done();ack_done();
        descriptor(1,2,1,1,BEATS,0,0);good_done();
        held_done={done_toggle,done_good,done_epoch,done_id,done_bank,done_crc,consumed_pixels};
        repeat(2*HT*VT+10)@(negedge clk);
        if(failed || request_toggle!=request_seen || held_done!==
            {done_toggle,done_good,done_epoch,done_id,done_bank,done_crc,consumed_pixels})
            $fatal(1,"unacknowledged result was overwritten or admitted a new lease");
        if(display_valid)$fatal(1,"previous success remained a sticky current-frame health claim");
        ack_done();descriptor(0,0,0,0,0,0,0);enable=0;
        repeat(HT*VT+10)@(negedge clk);
        if(failed || frame_active || display_valid || underflows!=0 || completed_frames!=3)$fatal(1,"blank grant is not normal blank");
        cases=cases+1;$display("PASS scan new/repeated ID, held lease/result metadata, ACK admission and blank grant");

        common_reset();descriptor(1,3,0,2,BEATS,0,0);good_done();ack_done();
        descriptor(1,4,1,3,BEATS,1,0);quarantine(8'h0a,0);
        if(completed_frames!=1 || mismatches!=1 || underflows!=0 || consumed_pixels!=N-1)
            $fatal(1,"good then bad CRC was reported healthy/complete");
        cases=cases+1;$display("PASS scan good then bad CRC revokes health/last/good and holds bad bank");

        common_reset();descriptor(1,10,0,4,BEATS,0,0);good_done();ack_done();
        descriptor(1,11,1,5,4,0,0);wait(failed);
        if(underflows!=1 || completed_frames!=1 || consumed_pixels!=64)$fatal(1,"starved frame accounting differs");
        load_words(5,4,BEATS-4);quarantine(8'h02,0);
        repeat(30)@(negedge clk);
        if(!rd_empty || rd_valid || dut.inflight!=0 || done_good || done_bank!=1 || done_id!=11)
            $fatal(1,"fault consumer failed to discard late DDR/FIFO tail while quarantined");
        cases=cases+1;$display("PASS scan good then underflow, continued FIFO tail drain and bank quarantine");

        common_reset();descriptor(1,20,0,6,BEATS,0,0);wait(case_pixels>=23);
        @(negedge clk);abort_fault=8'ha5;abort=1;wait(failed);@(negedge clk);
        if(fault!=8'ha5 || done_good || consumed_pixels!=case_pixels)$fatal(1,"midframe abort result/black accounting differs");
        wait(fifo_rd_en);common_reset();descriptor(1,1,1,7,BEATS,0,0);good_done();ack_done();
        cases=cases+1;$display("PASS scan midframe abort with inflight drain, coordinated reset and fresh frame recovery");

        common_reset();descriptor(1,1,0,8,BEATS,0,1);quarantine(8'h05,0);
        if(case_pixels!=0 || completed_frames!=0 || done_toggle!=0)$fatal(1,"old request epoch admitted a lease");
        cases=cases+1;$display("PASS scan old epoch rejected before output, FIFO drained without release");

        common_reset();descriptor(0,0,0,0,0,0,0);
        wait(dut.y==Y0 && dut.x==X0+4);@(negedge clk);
        grant_valid=1;grant_epoch=expected_epoch;grant_id=30;grant_bank=1;grant_checksum=crc_pixels(9,N);
        grant_toggle=!grant_toggle;quarantine(8'h03,0);
        if(case_pixels!=0 || completed_frames!=0)$fatal(1,"late grant emitted pixels");
        cases=cases+1;$display("PASS scan late closed-window grant rejected without new request/good");

        common_reset();descriptor(1,7,0,10,BEATS,0,0);good_done();ack_done();
        descriptor(1,6,1,11,BEATS,0,0);quarantine(8'h06,0);
        if(completed_frames!=1 || case_pixels!=0)$fatal(1,"older frame ID was accepted as new");
        cases=cases+1;$display("PASS scan older frame ID rejected while legal refresh/new IDs remain supported");

        common_reset();descriptor(1,40,1,12,BEATS,0,0);good_done();
        held_done={done_toggle,done_good,done_epoch,done_id,done_bank,done_crc,consumed_pixels};
        @(negedge clk);rogue_valid=1;rogue_data=256'hbad;@(negedge clk);rogue_valid=0;
        quarantine(8'h04,1);
        if(held_done!=={done_toggle,done_good,done_epoch,done_id,done_bank,done_crc,consumed_pixels})
            $fatal(1,"post-success fault overwrote unacknowledged result bus");
        ack_done();if(done_good || !failed)$fatal(1,"acked old good record kept a healthy flag after fault");
        cases=cases+1;$display("PASS scan post-success unsolicited FIFO return revokes health while held good bus is preserved");

        common_reset();force_ready_open=1;
        descriptor(1,50,0,13,BEATS+1,0,0);quarantine(8'h08,0);
        if(completed_frames!=0 || !rd_empty || dut.inflight!=0)$fatal(1,"extra queued word was published good or not drained");
        cases=cases+1;$display("PASS scan overlong FIFO stream fails final-count/empty check and drains");
        if(cases!=9 || good_events!=8 || bad_events<4 || ready_stalls==0 || return_latency_events==0 || requests==0 || returns==0)
            $fatal(1,"scan directed coverage was vacuous cases=%0d good=%0d bad=%0d",cases,good_events,bad_events);
        $display("SCAN_COVERAGE cases=%0d good=%0d bad=%0d fault_cases=%0d reads=%0d returns=%0d ready_stalls=%0d return_latency=%0d",cases,good_events,bad_events,fault_cases,requests,returns,ready_stalls,return_latency_events);
        begin : write_summary
            integer out;
            out=$fopen("summary.json","w");
            $fdisplay(out,"{\"passed\":true,\"width\":32,\"height\":16,\"cases\":%0d,\"good_frames\":%0d,\"bad_events\":%0d,\"fault_cases\":%0d,\"fifo_requests\":%0d,\"fifo_returns\":%0d,\"ready_stall_cycles\":%0d,\"return_latency_events\":%0d,\"real_synchronous_fifo\":true,\"native_timing_verified\":false,\"hardware_verified\":false}",cases,good_events,bad_events,fault_cases,requests,returns,ready_stalls,return_latency_events);
            $fclose(out);
        end
        $display("PASS board1080 scan: independent RGB565/CRC, held epochs/IDs, faults-black-drain, common reset; no PHY or hardware claim");
        $finish;
    end
endmodule
