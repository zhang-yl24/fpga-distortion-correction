`timescale 1ns/1ps
// Actual byte-wide DVP -> two independent parameterizations -> asynchronous
// FIFO -> independent pixel/CRC oracle. No HDMI capture RTL is an oracle.
module tb_dvp_rgb565_capture_cdc;
    localparam W=32, H=4, N=W*H, FRAME_WORDS=N/16;
    reg cam_clk=0, sys_clk=0;
    always #7 cam_clk=~cam_clk;
    always #4 sys_clk=~sys_clk;
    reg rst_n=0, enable=0, vs=0, href=0;
    reg [7:0] high_first_data=0, low_first_data=0;
    reg grant_valid=0, grant_bank=0; reg [31:0] grant_id=0;
    reg fifo_ready=0, done_ready=0;
    wire grant_ready, fifo_valid, fifo_idle, done_valid, done_good, done_bank;
    wire [255:0] fifo_data;
    wire [31:0] done_id, done_pixels, done_crc, no_grant_frames;
    wire [7:0] done_fault;
    wire other_grant_ready, other_fifo_valid, other_fifo_idle;
    wire other_done_valid, other_done_good, other_done_bank;
    wire [255:0] other_fifo_data;
    wire [31:0] other_done_id, other_done_pixels, other_done_crc, other_no_grant_frames;
    wire [7:0] other_done_fault;
    dvp_rgb565_capture_cdc #(.WIDTH(W),.HEIGHT(H),.FIFO_ADDR_BITS(2)) dut(
        .cam_clk(cam_clk),.sys_clk(sys_clk),.rst_n(rst_n),.enable(enable),
        .cam_vsync(vs),.cam_href(href),.cam_data(high_first_data),
        .grant_valid(grant_valid),.grant_ready(grant_ready),.grant_bank(grant_bank),.grant_id(grant_id),
        .fifo_valid(fifo_valid),.fifo_ready(fifo_ready),.fifo_data(fifo_data),.fifo_idle(fifo_idle),
        .done_valid(done_valid),.done_ready(done_ready),.done_good(done_good),.done_bank(done_bank),
        .done_id(done_id),.done_pixels(done_pixels),.done_crc(done_crc),.done_fault(done_fault),
        .no_grant_frames(no_grant_frames));
    dvp_rgb565_capture_cdc #(.WIDTH(W),.HEIGHT(H),.FIFO_ADDR_BITS(2),
        .VSYNC_ACTIVE_HIGH(0),.HREF_ACTIVE_HIGH(0),.HIGH_BYTE_FIRST(0)) alternate(
        .cam_clk(cam_clk),.sys_clk(sys_clk),.rst_n(rst_n),.enable(enable),
        .cam_vsync(!vs),.cam_href(!href),.cam_data(low_first_data),
        .grant_valid(grant_valid),.grant_ready(other_grant_ready),.grant_bank(grant_bank),.grant_id(grant_id),
        .fifo_valid(other_fifo_valid),.fifo_ready(fifo_ready),.fifo_data(other_fifo_data),.fifo_idle(other_fifo_idle),
        .done_valid(other_done_valid),.done_ready(done_ready),.done_good(other_done_good),.done_bank(other_done_bank),
        .done_id(other_done_id),.done_pixels(other_done_pixels),.done_crc(other_done_crc),.done_fault(other_done_fault),
        .no_grant_frames(other_no_grant_frames));

    integer ticks=0, seed=1, words=0, cases=0, stall_cycles=0;
    integer good_file, grant_count=0, done_count=0;
    reg force_stall=0, check_words=1, dump_good=0;
    reg held_word=0, held_done=0;
    reg [255:0] prior_word;
    reg [105:0] prior_done;
    function automatic [15:0] pixel(input integer index, input integer s);
        begin pixel=(16'h1234 + index*16'h0103 + s*16'h0711) & 16'hffff; end
    endfunction
    // Bit-at-a-time bitstream oracle, independently ordered from DUT's nested
    // byte function. The Python runner also checks dumped words using zlib.
    function automatic [31:0] expected_crc(input integer s);
        reg [31:0] c; reg [15:0] p; reg feedback; integer i, bit_index;
        begin
            c=32'hffffffff;
            for(i=0;i<N;i=i+1) begin
                p=pixel(i,s);
                for(bit_index=0;bit_index<16;bit_index=bit_index+1) begin
                    feedback=c[0]^p[bit_index]; c=c>>1;
                    if(feedback) c=c^32'hedb88320;
                end
            end
            expected_crc=~c;
        end
    endfunction
    always @(negedge sys_clk) begin
        ticks=ticks+1;
        if(ticks>200000) $fatal(1,"DVP capture bounded system-cycle timeout");
        fifo_ready=rst_n && !force_stall && ticks%7>=3;
    end
    always @(posedge sys_clk) begin
        if(!rst_n) begin held_word<=0; held_done<=0; end
        else begin
            if({grant_ready,fifo_valid,fifo_idle,done_valid,no_grant_frames} !==
               {other_grant_ready,other_fifo_valid,other_fifo_idle,other_done_valid,other_no_grant_frames})
                $fatal(1,"byte order/polarity parameterizations differ in handshakes");
            if(fifo_valid && fifo_data!==other_fifo_data)
                $fatal(1,"byte order/polarity parameterizations differ in FIFO data");
            if(done_valid && {done_good,done_bank,done_id,done_pixels,done_crc,done_fault} !==
               {other_done_good,other_done_bank,other_done_id,other_done_pixels,other_done_crc,other_done_fault})
                $fatal(1,"byte order/polarity parameterizations differ in completion");
            if(held_word && (!fifo_valid || fifo_data!==prior_word))
                $fatal(1,"FIFO payload changed under backpressure");
            if(held_done && (!done_valid || {done_good,done_bank,done_id,done_pixels,done_crc,done_fault}!==prior_done))
                $fatal(1,"completion metadata changed under backpressure");
            held_word<=fifo_valid && !fifo_ready; prior_word<=fifo_data;
            held_done<=done_valid && !done_ready;
            prior_done<={done_good,done_bank,done_id,done_pixels,done_crc,done_fault};
            if(fifo_valid && !fifo_ready) stall_cycles=stall_cycles+1;
            if(grant_valid && grant_ready) grant_count=grant_count+1;
            if(done_valid && done_ready) done_count=done_count+1;
            if(fifo_valid && fifo_ready) begin
                if(check_words) begin
                    if(words>=FRAME_WORDS) $fatal(1,"too many FIFO words in good frame");
                    for(integer lane=0;lane<16;lane=lane+1)
                        if(fifo_data[lane*16+:16]!==pixel(words*16+lane,seed))
                            $fatal(1,"independent byte/pack oracle mismatch word=%0d lane=%0d expected=%h actual=%h",
                                words,lane,pixel(words*16+lane,seed),fifo_data[lane*16+:16]);
                end
                if(dump_good) $fdisplay(good_file,"%064h",fifo_data);
                words=words+1;
            end
        end
    end
    task automatic mark_case(input string name);
        begin cases=cases+1; $display("DVP_CDC_CASE %s PASS",name); end
    endtask
    task automatic reset_all;
        begin
            @(negedge sys_clk); rst_n=0; enable=0; grant_valid=0; done_ready=0;
            force_stall=0; dump_good=0;
            @(negedge cam_clk); vs=0; href=0; high_first_data=0; low_first_data=0;
            repeat(8) @(negedge sys_clk);
            rst_n=1; repeat(10) @(negedge cam_clk);
            if(!grant_ready || done_valid || fifo_valid || !fifo_idle || no_grant_frames!=0)
                $fatal(1,"common reset left stale reservation/FIFO/completion/counter");
            words=0; check_words=1;
            enable=1; repeat(5) @(negedge cam_clk);
        end
    endtask
    task automatic offer_grant(input bit bank, input [31:0] id);
        begin
            wait(grant_ready); @(negedge sys_clk);
            grant_bank=bank; grant_id=id; grant_valid=1;
            @(negedge sys_clk); grant_valid=0;
            repeat(6) @(negedge cam_clk);
            if(grant_ready) $fatal(1,"grant was not reserved until completion");
        end
    endtask
    task automatic boundary;
        begin
            @(negedge cam_clk); href=0; vs=1;
            repeat(3) @(negedge cam_clk); vs=0;
            repeat(5) @(negedge cam_clk);
        end
    endtask
    task automatic send_byte(input integer pixel_index, input integer second);
        reg [15:0] p;
        begin
            p=pixel(pixel_index,seed);
            @(negedge cam_clk); href=1;
            high_first_data=second ? p[7:0] : p[15:8];
            low_first_data=second ? p[15:8] : p[7:0];
        end
    endtask
    task automatic row(input integer y, input integer bytes_in_row);
        begin
            for(integer i=0;i<bytes_in_row;i=i+1) send_byte(y*W+i/2,i%2);
            @(negedge cam_clk); href=0;
            repeat(5) @(negedge cam_clk);
        end
    endtask
    task automatic frame(input integer number_of_rows, input integer first_row_bytes);
        begin
            boundary();
            for(integer y=0;y<number_of_rows;y=y+1) row(y,y==0 ? first_row_bytes : 2*W);
            boundary();
        end
    endtask
    task automatic finish(input bit good, input [7:0] fault_mask, input integer count,
                          input bit bank, input [31:0] id);
        begin
            wait(done_valid); @(negedge sys_clk);
            if(done_good!==good || (done_fault&fault_mask)!==fault_mask ||
               (good && done_fault!=0) || done_pixels!=count || done_bank!==bank || done_id!==id)
                $fatal(1,"completion expected good=%0d faultmask=%h pixels=%0d bank=%0d id=%h; actual %0d/%h/%0d/%0d/%h",
                    good,fault_mask,count,bank,id,done_good,done_fault,done_pixels,done_bank,done_id);
            if(good && done_crc!==expected_crc(seed))
                $fatal(1,"independent CRC expected=%h actual=%h",expected_crc(seed),done_crc);
            if(grant_ready) $fatal(1,"unacknowledged completion released reservation");
            wait(fifo_idle); repeat(13) @(negedge sys_clk);
            if(good && words!=FRAME_WORDS) $fatal(1,"missing words before good completion acknowledged");
            if(dump_good) $display("DVP_CDC_GOOD pixels=%0d crc=%08h bank=%0d id=%08h",done_pixels,done_crc,done_bank,done_id);
            done_ready=1; @(negedge sys_clk); done_ready=0;
            repeat(8) @(negedge cam_clk);
            if(done_valid || !grant_ready || !fifo_idle) $fatal(1,"completion did not retire cleanly");
        end
    endtask
    task automatic good_frame(input integer s, input bit bank, input [31:0] id);
        begin
            seed=s; words=0; check_words=1;
            offer_grant(bank,id); frame(H,2*W); finish(1,0,N,bank,id);
        end
    endtask
    task automatic bad_geometry(input integer kind, input string name);
        integer rows_to_send, bytes_first, expected_pixels; reg [7:0] required_fault;
        begin
            seed=10+kind; words=0; check_words=0;
            rows_to_send=H; bytes_first=2*W; expected_pixels=N; required_fault=0;
            case(kind)
                1:begin bytes_first=2*W-2; expected_pixels=N-1; required_fault=8'h05; end
                2:begin bytes_first=2*W+2; expected_pixels=N+1; required_fault=8'h03; end
                3:begin rows_to_send=H-1; expected_pixels=N-W; required_fault=8'h04; end
                4:begin rows_to_send=H+1; expected_pixels=N+W; required_fault=8'h06; end
                5:begin bytes_first=2*W-1; expected_pixels=N-1; required_fault=8'h41; end
            endcase
            offer_grant(0,kind); frame(rows_to_send,bytes_first);
            finish(0,required_fault,expected_pixels,0,kind);
            mark_case(name);
            good_frame(30+kind,1,32'h100+kind);
        end
    endtask
    integer before_no_grant, before_done, before_words;
    initial begin
        good_file=$fopen("dvp-good-words.hex","w");
        if(good_file==0) $fatal(1,"cannot open good-frame raw word evidence");
        reset_all(); dump_good=1;
        good_frame(1,1,32'h10203040); dump_good=0; $fclose(good_file);
        if(stall_cycles==0) $fatal(1,"backpressure coverage missing");
        mark_case("two_byte_pixels_pack_crc_async_backpressure");
        mark_case("low_byte_first_active_low_vsync_href");

        // No reservation when the first byte arrives: one whole frame is
        // ignored, even though the late mailbox arrives before its second row.
        seed=2; words=0; before_no_grant=no_grant_frames; before_done=done_count;
        boundary(); row(0,2*W); offer_grant(0,32'h20304050);
        for(integer y=1;y<H;y=y+1) row(y,2*W);
        boundary(); repeat(15) @(negedge sys_clk);
        if(done_valid || words!=0 || no_grant_frames!=before_no_grant+1 || done_count!=before_done || grant_ready)
            $fatal(1,"late grant captured tail of an unreserved frame or was lost");
        seed=3; frame(H,2*W); finish(1,0,N,0,32'h20304050);
        mark_case("late_grant_waits_for_next_whole_frame");

        // No grant at all never produces data/completion and counts once per
        // active frame, not once per byte, line or idle VSYNC.
        words=0; before_no_grant=no_grant_frames;
        frame(H,2*W); frame(H,2*W); boundary();
        repeat(15) @(negedge sys_clk);
        if(words!=0 || done_valid || no_grant_frames!=before_no_grant+2)
            $fatal(1,"no-grant frame accounting/whole-frame discard failed");
        mark_case("missing_grant_counts_whole_active_frames");

        bad_geometry(1,"short_line_rejected"); bad_geometry(2,"long_line_rejected");
        bad_geometry(3,"short_frame_rejected"); bad_geometry(4,"long_frame_rejected");
        bad_geometry(5,"odd_byte_line_rejected_no_cross_line_pair");
        mark_case("good_frame_recovery_after_each_geometry_fault_without_reset");

        // VSYNC in the middle of a pixel is both a framing error and an
        // incomplete byte pair. Keep HREF high across the edge deliberately.
        seed=50; words=0; check_words=0; offer_grant(1,32'h5050); boundary();
        send_byte(0,0); send_byte(0,1); send_byte(1,0);
        @(negedge cam_clk); vs=1;
        repeat(3) @(negedge cam_clk); vs=0; href=0;
        finish(0,8'h54,1,1,32'h5050);
        good_frame(51,0,32'h5151);
        mark_case("vsync_interrupt_discards_half_pixel_and_recovers");

        // Revoking admission mid-frame makes completion bad even after enable
        // returns. It never resets/withdraws already queued FIFO words.
        seed=60; words=0; check_words=0; offer_grant(0,32'h6060); boundary();
        row(0,2*W); enable=0; repeat(6) @(negedge cam_clk); enable=1;
        repeat(6) @(negedge cam_clk);
        for(integer y=1;y<H;y=y+1) row(y,2*W);
        boundary(); finish(0,8'h20,N,0,32'h6060);
        good_frame(61,1,32'h6161);
        mark_case("enable_loss_sticky_until_failed_frame_retired");

        // Depth four plus the read holding register cannot hold eight words.
        // The source is unthrottled, so overflow must invalidate the frame.
        seed=70; words=0; check_words=0; force_stall=1;
        offer_grant(1,32'h7070); frame(H,2*W);
        wait(done_valid); repeat(8) @(negedge sys_clk);
        if(done_good || !(done_fault&8'h08) || fifo_idle || !fifo_valid || grant_ready)
            $fatal(1,"overflow did not preserve failed reservation and queued tail");
        force_stall=0; finish(0,8'h08,N,1,32'h7070);
        if(words<1 || words>=FRAME_WORDS) $fatal(1,"overflow test did not exercise partial FIFO output");
        good_frame(71,0,32'h7171);
        mark_case("fifo_overflow_failed_frame_drain_and_recovery");

        // Hold both data and completion while another unreserved frame passes.
        // No second completion or metadata overwrite is legal.
        seed=80; words=0; check_words=0; force_stall=1;
        offer_grant(0,32'h8080); frame(H,2*W); wait(done_valid);
        before_no_grant=no_grant_frames; frame(H,2*W);
        if(done_id!==32'h8080 || no_grant_frames!=before_no_grant+1)
            $fatal(1,"unacknowledged completion overwritten or dropped frame uncounted");
        force_stall=0; finish(0,8'h08,N,0,32'h8080);
        mark_case("completion_mailbox_stable_across_dropped_frame");

        seed=90; words=0; check_words=0; offer_grant(1,32'h9090); boundary();
        send_byte(0,0); @(posedge cam_clk); #1;
        if(!dut.half_byte || !alternate.half_byte) $fatal(1,"half-pixel reset precondition missing");
        rst_n=0;
        reset_all(); good_frame(91,0,32'h9191);
        mark_case("common_reset_discards_half_pixel_and_reservation");

        seed=92; words=0; check_words=0; force_stall=1;
        offer_grant(1,32'h9292); boundary(); row(0,2*W); wait(fifo_valid);
        reset_all(); good_frame(93,1,32'h9393);
        mark_case("common_reset_discards_queued_payload_and_restarts");

        if(cases!=16) $fatal(1,"case coverage count mismatch: %0d",cases);
        $display("DVP_CDC_SUMMARY cases=%0d stall_cycles=%0d grants=%0d completions=%0d",cases,stall_cycles,grant_count,done_count);
        $display("PASS dvp_rgb565_capture_cdc"); $finish;
    end
endmodule
