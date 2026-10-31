`timescale 1ns/1ps
module tb_hdmi_diag_uart_v3;
    localparam REF_HZ=1000000, BAUD=100000, BIT_NS=10000;
    reg ref_clk=0, cfg_clk=0, rst_n=0;
    always #500 ref_clk=~ref_clk;
    always #700 cfg_clk=~cfg_clk;
    reg [4:0] observer_freshness=5'b10101;
    reg [15:0] vs_edge_count_ref=16'hfffe;
    wire uart_txd, record_started, record_done;
    wire [31:0] record_sequence;
    hdmi_diag_uart_v3 #(.REF_CLOCK_HZ(REF_HZ),.BAUD(BAUD),.REPORT_CYCLES(500),
        .CFG_SNAPSHOT_CYCLES(37),.CFG_STALE_CYCLES(150)) dut(
        .ref_clk(ref_clk),.cfg_clk(cfg_clk),.rst_n(rst_n),
        .cfg_rx_done(1'b0),.cfg_all_done(1'b0),.cfg_failed(1'b0),.cfg_error(4'b0),
        .cfg_transactions(32'b0),.cfg_last_address(16'b0),.cfg_last_value(8'b0),.cfg_last_meta(2'b0),
        .cfg_lock_ref(1'b0),.video_lock_ref(1'b0),.observer_released(1'b0),
        .input_qualified(1'b0),.input_failed(1'b0),.input_fault(8'b0),
        .polarity_known_ref(1'b0),.vs_inactive_ref(1'b0),.hs_inactive_ref(1'b0),
        .measured_width(16'b0),.measured_height(16'b0),.pclk_edges_per_window(32'b0),
        .good_frames(32'b0),.bad_frames(32'b0),.observer_freshness(observer_freshness),
        .vs_edge_count_ref(vs_edge_count_ref),
        .uart_txd(uart_txd),.record_started(record_started),.record_done(record_done),
        .record_sequence(record_sequence));

    reg [7:0] frame[0:63];
    integer frame_count=0;
    integer wire_file;
    reg [7:0] sample;
    integer bit_index;
    task automatic receive_frame;
        begin
            for(integer n=0;n<64;n=n+1) begin
                @(negedge uart_txd);
                #(BIT_NS/2);
                if(uart_txd!==1'b0)$fatal(1,"start bit invalid");
                for(bit_index=0;bit_index<8;bit_index=bit_index+1) begin
                    #(BIT_NS); sample[bit_index]=uart_txd;
                end
                #(BIT_NS);
                if(uart_txd!==1'b1)$fatal(1,"stop bit invalid");
                frame[n]=sample;
                $fwrite(wire_file,"%c",sample);
                #1;
            end
            frame_count=frame_count+1;
        end
    endtask
    function automatic [31:0] read32(input integer offset);
        read32={frame[offset+3],frame[offset+2],frame[offset+1],frame[offset]};
    endfunction
    function automatic [31:0] crc32_body;
        reg [31:0] c;
        reg feedback;
        begin
            c=32'hffffffff;
            for(integer n=0;n<56;n=n+1)
                for(integer b=0;b<8;b=b+1) begin
                    feedback=c[0]^frame[n][b];c=c>>1;
                    if(feedback)c=c^32'hedb88320;
                end
            crc32_body=~c;
        end
    endfunction
    task automatic check_frame(input [7:0] wanted_freshness,input [15:0] wanted_vs_count,
                               input [31:0] wanted_sequence);
        begin
            if(frame[0]!=="P" || frame[1]!=="G" || frame[2]!=="H" || frame[3]!=="D" ||
               frame[4]!=="M" || frame[5]!=="I" || frame[6]!=="0" || frame[7]!=="1" ||
               read32(8)!==wanted_sequence || read32(48)!==32'h48444903 ||
               frame[52]!==wanted_freshness || {frame[54],frame[53]}!==wanted_vs_count || frame[55]!==0)
                $fatal(1,"version, observer freshness or VS count payload differs");
            if(read32(56)!==crc32_body() || read32(60)!==32'h31304d48)
                $fatal(1,"CRC or trailer differs");
        end
    endtask
    initial begin
        wire_file=$fopen("hdmi-status-wire.bin","wb");
        if(wire_file==0)$fatal(1,"cannot create v3 wire evidence file");
        repeat(8) @(negedge ref_clk);
        rst_n=1;
        receive_frame();check_frame(8'h15,16'hfffe,1);
        $display("HDMI_UART_CASE v3_packet_freezes_mid_record_updates PASS");
        receive_frame();check_frame(8'h0a,16'hffff,2);
        receive_frame();check_frame(8'h1f,16'h0000,3);
        $display("HDMI_UART_CASE v3_vs_counter_16bit_wrap_preserved PASS");
        receive_frame();check_frame(8'h00,16'h1234,4);
        $display("HDMI_UART_CASE v3_vs_counter_little_endian_payload PASS");
        if(frame_count!=4)$fatal(1,"wire receiver coverage is incomplete");
        $fclose(wire_file);
        $display("PASS hdmi_diag_uart_v3");
        $finish;
    end
    // Change both extension fields only after each record has been latched.
    // The independent wire receiver above must still see the old tuple for
    // that entire record, followed by the new tuple in the next record.
    initial begin
        @(posedge record_started);@(negedge ref_clk);
        observer_freshness=5'b01010;vs_edge_count_ref=16'hffff;
        @(posedge record_started);@(negedge ref_clk);
        observer_freshness=5'b11111;vs_edge_count_ref=16'h0000;
        @(posedge record_started);@(negedge ref_clk);
        observer_freshness=5'b00000;vs_edge_count_ref=16'h1234;
    end
    initial begin
        #200000000;$fatal(1,"bounded UART simulation timeout");
    end
endmodule
