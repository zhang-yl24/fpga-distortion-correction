`timescale 1ns/1ps
// Diagnostic transport only. Monitor inputs are reference-domain stimuli;
// this bench does not replace the existing real-raster input_status tests.
// Received bytes below are decoded exclusively from the UART wire, including
// deliberately injected line noise and a reset-truncated packet. No byte-level
// DUT handshake/data is used as received evidence.
module tb_hdmi_diag_uart;
    localparam REF_HZ=1000000, BAUD=100000, BIT_CYCLES=10;
    localparam integer BIT_NS=10000, SNAPSHOT_CYCLES=37, STALE_CYCLES=150;
    reg ref_clk=0, cfg_clk=0, run_cfg=0;
    always #500 ref_clk=~ref_clk;
    always #700 if(run_cfg) cfg_clk=~cfg_clk;
    reg rst_n=0;
    reg cfg_rx_done=0, cfg_all_done=0, cfg_failed=0;
    reg [3:0] cfg_error=0;
    reg [31:0] cfg_transactions=0;
    reg [15:0] cfg_last_address=0;
    reg [7:0] cfg_last_value=0;
    reg [1:0] cfg_last_meta=0;
    reg cfg_lock_ref=0, video_lock_ref=0, observer_released=0;
    reg input_qualified=0, input_failed=0;
    reg [7:0] input_fault=0;
    reg polarity_known_ref=0, vs_inactive_ref=0, hs_inactive_ref=0;
    reg [15:0] measured_width=0, measured_height=0;
    reg [31:0] pclk_edges_per_window=0, good_frames=0, bad_frames=0;
    wire uart_txd, record_started, record_done;
    wire [31:0] record_sequence;
    hdmi_diag_uart #(.REF_CLOCK_HZ(REF_HZ),.BAUD(BAUD),.REPORT_CYCLES(500),
        .CFG_SNAPSHOT_CYCLES(SNAPSHOT_CYCLES),.CFG_STALE_CYCLES(STALE_CYCLES)) dut(.*);

    reg noise_mode=1, noise_line=1, allow_truncation=0;
    wire observed_uart=noise_mode ? noise_line : uart_txd;
    reg [7:0] received[0:16383];
    integer received_count=0, cursor=0, valid_records=0, rejected_candidates=0;
    integer wire_file, cases=0, cfg_edges=0, ref_cycles=0;
    integer record_done_count=0, framing_errors=0;
    time last_stop_center=0, record_start_time=0;
    reg [7:0] decoded_byte;
    always @(posedge cfg_clk) cfg_edges=cfg_edges+1;
    always @(posedge ref_clk) begin
        ref_cycles=ref_cycles+1;
        if(ref_cycles>300000) $fatal(1,"HDMI UART bounded reference-cycle timeout");
        if(record_started) record_start_time=$time;
        if(record_done) begin
            if(uart_txd!==1'b1 || $time<last_stop_center+BIT_NS/2 ||
               $time<record_start_time+64*10*BIT_NS)
                $fatal(1,"record_done preceded the last full UART stop bit");
            record_done_count=record_done_count+1;
        end
    end
    // Independent 8N1 receiver: detect start, sample at bit centres, require
    // stop high. The transmitter reset can legitimately truncate one byte.
    initial begin
        forever begin
            @(negedge observed_uart);
            #(BIT_NS/2);
            if(observed_uart===1'b0) begin
                for(integer b=0;b<8;b=b+1) begin
                    #(BIT_NS); decoded_byte[b]=observed_uart;
                end
                #(BIT_NS);
                if(observed_uart!==1'b1) begin
                    framing_errors=framing_errors+1;
                    if(!allow_truncation) $fatal(1,"UART stop bit invalid without reset injection");
                end else begin
                    if(received_count>=16384) $fatal(1,"wire evidence buffer exceeded");
                    received[received_count]=decoded_byte;
                    received_count=received_count+1;
                    $fwrite(wire_file,"%c",decoded_byte);
                    last_stop_center=$time;
                end
                #(BIT_NS/2);
            end else if(!allow_truncation) $fatal(1,"UART start bit too short");
        end
    end
    function automatic [31:0] read32(input integer offset);
        begin read32={received[offset+3],received[offset+2],received[offset+1],received[offset]}; end
    endfunction
    function automatic [15:0] read16(input integer offset);
        begin read16={received[offset+1],received[offset]}; end
    endfunction
    function automatic magic_matches(input integer offset);
        reg [63:0] magic;
        begin
            magic=64'h3130494d44484750; magic_matches=1;
            for(integer i=0;i<8;i=i+1)
                if(received[offset+i]!==magic[i*8+:8]) magic_matches=0;
        end
    endfunction
    function automatic record_matches(input integer offset);
        reg [31:0] c; reg feedback;
        begin
            record_matches=magic_matches(offset);
            c=32'hffffffff;
            for(integer i=0;i<56;i=i+1)
                for(integer b=0;b<8;b=b+1) begin
                    feedback=c[0]^received[offset+i][b]; c=c>>1;
                    if(feedback) c=c^32'hedb88320;
                end
            if(read32(offset+56)!==~c || read32(offset+60)!==32'h31304d48 ||
               read32(offset+48)!==32'h48444901 || read32(offset+52)!==0 ||
               (read16(offset+16)&16'he000)!==0 || received[offset+18][7:4]!==0 ||
               received[offset+47][7:2]!==0) record_matches=0;
        end
    endfunction
    task automatic await_record(output integer offset);
        begin: scan
            forever begin
                while(received_count<cursor+64) @(negedge ref_clk);
                if(record_matches(cursor)) begin
                    offset=cursor; cursor=cursor+64; valid_records=valid_records+1;
                    disable scan;
                end
                if(magic_matches(cursor)) rejected_candidates=rejected_candidates+1;
                cursor=cursor+1;
            end
        end
    endtask
    task automatic await_sequence(input [31:0] wanted, output integer offset);
        begin: scan
            forever begin
                await_record(offset);
                if(read32(offset+8)==wanted) disable scan;
            end
        end
    endtask
    task automatic mark_case(input string name);
        begin cases=cases+1; $display("HDMI_UART_CASE %s PASS",name); end
    endtask
    task automatic noise_byte(input [7:0] value);
        begin
            noise_line=0; #(BIT_NS);
            for(integer b=0;b<8;b=b+1) begin noise_line=value[b]; #(BIT_NS); end
            noise_line=1; #(BIT_NS); #(BIT_NS);
        end
    endtask
    task automatic next_record_start(output reg [31:0] seq_value);
        begin @(posedge record_started); #1; seq_value=record_sequence; end
    endtask
    task automatic clear_inputs;
        begin
            cfg_rx_done=0; cfg_all_done=0; cfg_failed=0; cfg_error=0;
            cfg_transactions=0; cfg_last_address=0; cfg_last_value=0; cfg_last_meta=0;
            cfg_lock_ref=0; video_lock_ref=0; observer_released=0;
            input_qualified=0; input_failed=0; input_fault=0;
            polarity_known_ref=0; vs_inactive_ref=0; hs_inactive_ref=0;
            measured_width=0; measured_height=0; pclk_edges_per_window=0; good_frames=0; bad_frames=0;
        end
    endtask
    integer offset, truncate_base;
    reg [31:0] target_sequence;
    reg [15:0] f;
    initial begin
        wire_file=$fopen("hdmi-status-wire.bin","wb");
        if(wire_file==0) $fatal(1,"cannot open UART wire evidence file");
        repeat(8) @(negedge ref_clk);
        noise_byte(8'h00); noise_byte(8'h7e); noise_byte(8'h55);
        if(received_count!=3 || received[0]!==8'h00 || received[1]!==8'h7e || received[2]!==8'h55)
            $fatal(1,"independent receiver failed initial known wire bytes");
        noise_mode=0;
        @(negedge ref_clk); rst_n=1;
        next_record_start(target_sequence);
        // All reference fields change after the snapshot, before the packet
        // body has reached the receiver. Packet one must remain all-zero status.
        @(negedge ref_clk);
        cfg_lock_ref=1; video_lock_ref=1; observer_released=1;
        polarity_known_ref=1; input_qualified=1;
        measured_width=1920; measured_height=1080; pclk_edges_per_window=74250;
        good_frames=2;
        await_sequence(target_sequence,offset);
        if(target_sequence!=1 || cfg_edges!=0 || read16(offset+16)!==0 ||
           read32(offset+36)!==32'hffffffff || read32(offset+40)!==0 ||
           read16(offset+20)!==0 || read16(offset+22)!==0 ||
           read32(offset+24)!==0 || read32(offset+28)!==0 ||
           received[offset+18]!==0 || received[offset+19]!==0)
            $fatal(1,"cold UART packet depended on cfg clock or changed after snapshot");
        mark_case("startup_without_cfg_clock_reports_unknown");

        @(negedge ref_clk);
        cfg_rx_done=1; cfg_all_done=1; cfg_failed=0; cfg_error=0;
        cfg_transactions=32'h11223344; cfg_last_address=16'h1281;
        cfg_last_value=8'h04; cfg_last_meta=2'b10; run_cfg=1;
        repeat(200) @(negedge ref_clk);
        next_record_start(target_sequence);
        @(negedge ref_clk);
        input_qualified=0; input_failed=1; input_fault=8'h12;
        measured_width=1111; measured_height=222; pclk_edges_per_window=12345;
        good_frames=19; bad_frames=3; vs_inactive_ref=1; hs_inactive_ref=1;
        @(negedge cfg_clk);
        cfg_rx_done=0; cfg_all_done=0; cfg_failed=1; cfg_error=4'ha;
        cfg_transactions=32'h11223345; cfg_last_address=16'h209e;
        cfg_last_value=8'h02; cfg_last_meta=2'b01;
        await_sequence(target_sequence,offset); f=read16(offset+16);
        if(f[6:0]!==7'b0111111 || f[12:7]!==6'b000111 || received[offset+18]!==0 ||
           received[offset+19]!==0 || read16(offset+20)!==1920 || read16(offset+22)!==1080 ||
           read32(offset+24)!==74250 || read32(offset+28)!==2 || read32(offset+32)!==0 ||
           read32(offset+40)!==32'h11223344 || read16(offset+44)!==16'h1281 ||
           received[offset+46]!==8'h04 || received[offset+47]!==8'h02)
            $fatal(1,"a UART packet mixed reference/config fields from different snapshots flags=%h",f);
        mark_case("whole_record_snapshot_stable_during_uart");

        next_record_start(target_sequence);
        await_sequence(target_sequence,offset); f=read16(offset+16);
        if(!f[0] || !f[1] || f[4] || f[5] || !f[6] || received[offset+18]!==8'h0a ||
           read32(offset+40)!==32'h11223345 || read16(offset+44)!==16'h209e ||
           received[offset+46]!==8'h02 || received[offset+47]!==8'h01)
            $fatal(1,"65-bit cfg snapshot tore across init/fault/code/transaction fields");
        mark_case("cfg_65bit_snapshot_and_fault_code_coherent");
        if(!f[7] || !f[8] || f[9] || !f[10] || !f[11] || !f[12] ||
           received[offset+19]!==8'h12 || read16(offset+20)!==1111 || read16(offset+22)!==222 ||
           read32(offset+24)!==12345 || read32(offset+28)!==19 || read32(offset+32)!==3)
            $fatal(1,"input observer status confused with init completion/error");
        mark_case("input_monitor_fields_distinct_from_iic_completion");

        @(negedge cfg_clk); run_cfg=0;
        @(negedge ref_clk); input_fault=8'h25; pclk_edges_per_window=0;
        repeat(STALE_CYCLES+50) @(negedge ref_clk);
        next_record_start(target_sequence);
        await_sequence(target_sequence,offset); f=read16(offset+16);
        if(!f[0] || f[1] || !f[6] || received[offset+18]!==8'h0a ||
           read32(offset+36)<STALE_CYCLES || read32(offset+40)!==32'h11223345 ||
           received[offset+19]!==8'h25 || read32(offset+24)!==0)
            $fatal(1,"stopped cfg clock blocked UART or falsely refreshed held status");
        mark_case("cfg_stopped_clock_stale_keeps_uart_running");

        @(negedge ref_clk); run_cfg=1;
        repeat(200) @(negedge ref_clk);
        next_record_start(target_sequence);
        await_sequence(target_sequence,offset); f=read16(offset+16);
        if(!f[0] || !f[1] || !f[6] || received[offset+18]!==8'h0a ||
           read32(offset+36)>=STALE_CYCLES || read32(offset+40)!==32'h11223345)
            $fatal(1,"cfg clock resume did not retire pending request and refresh snapshot");
        mark_case("cfg_clock_resume_refreshes_without_uart_reset");
        if(record_done_count<5) $fatal(1,"last stop-bit completion coverage missing");
        mark_case("record_done_waits_for_full_last_stop_bit");

        // Reset after the next packet's magic and part of its body are on the
        // wire, mid data byte. Preserve these actual decoded bytes in the file.
        next_record_start(target_sequence); truncate_base=received_count;
        wait(received_count>=truncate_base+20);
        #(2*BIT_NS+BIT_NS/3); allow_truncation=1; rst_n=0; clear_inputs();
        #(12*BIT_NS);
        noise_mode=1; noise_line=1;
        noise_byte(8'haa); noise_byte(8'h00); noise_mode=0;
        @(negedge ref_clk); rst_n=1; allow_truncation=0;
        next_record_start(target_sequence);
        if(target_sequence!=1) $fatal(1,"common reset did not restart record sequence");
        await_sequence(1,offset);
        if(read16(offset+16)!==0 || received[offset+18]!==0 || received[offset+19]!==0 ||
           read32(offset+40)!==0 || read16(offset+20)!==0 || read16(offset+22)!==0 ||
           rejected_candidates<1)
            $fatal(1,"reset-truncated packet was not rejected/resynchronized or old status survived");
        mark_case("reset_truncated_packet_resynchronizes_and_clears_status");
        @(posedge record_done); @(negedge ref_clk);
        if(valid_records<7 || received_count<64*7 || cases!=8)
            $fatal(1,"wire/packet test coverage vacuous");
        $fclose(wire_file);
        $display("HDMI_UART_SUMMARY cases=%0d decoded_bytes=%0d valid_records=%0d rejected_candidates=%0d record_done=%0d framing_errors=%0d",
            cases,received_count,valid_records,rejected_candidates,record_done_count,framing_errors);
        $display("PASS hdmi_diag_uart"); $finish;
    end
endmodule
