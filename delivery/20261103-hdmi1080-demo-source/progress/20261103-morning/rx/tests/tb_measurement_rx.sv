`timescale 1ps/1ps
module tb_measurement_rx;
    localparam CLOCK_HZ=27000000,BAUD=115200,BIT_CYCLES=(CLOCK_HZ+BAUD/2)/BAUD;
    localparam TIMEOUT=10000;
    reg clk=0,core_clk=0,rst_n=0,serial_rx=1;
    always #18518 clk=~clk;
    always #4000 core_clk=~core_clk;
    wire tx_on,tx_off,tx_before;
    wire [31:0] off_q,off_r,off_b,off_t,off_d,old_q,old_r,old_b,old_t,old_d;
    telemetry_uart_link #(.WIDTH(16),.HEIGHT(16),.CLOCK_HZ(CLOCK_HZ),.BAUD(BAUD),
        .RX_TIMEOUT_CYCLES(TIMEOUT),.STATS_ENABLE(1),.STATS_LIGHT(1)) enabled(
        .ctrl_clk(clk),.pix_clk(core_clk),.rst_n(rst_n),.uart_rx(serial_rx),.uart_tx(tx_on),
        .snapshot_core_clk(core_clk),.stats_request_ready(1'b1),.stats_response_valid(1'b0),.stats_response_body(640'd0),
        .snapshot_request_ready(1'b0),.snapshot_stop_ready(1'b0),.snapshot_ack_valid(1'b0),.snapshot_ack_body(352'd0),
        .snapshot_byte_valid(1'b0),.snapshot_byte_data(8'd0),.snapshot_release_valid(1'b0),
        .pixel_valid(1'b0),.frame_start(1'b0),.frame_last(1'b0),.video_abort(1'b0),
        .pixel_x(16'd0),.pixel_y(16'd0),.pixel_rgb(24'd0),.metadata_valid(1'b0),
        .scan_epoch(32'd0),.frame_id(32'd0),.param_id(32'd0),.bank(1'b0),.mode(8'd0));
    telemetry_uart_link #(.WIDTH(16),.HEIGHT(16),.CLOCK_HZ(CLOCK_HZ),.BAUD(BAUD),
        .RX_TIMEOUT_CYCLES(TIMEOUT),.STATS_ENABLE(0),.STATS_LIGHT(1)) disabled(
        .ctrl_clk(clk),.pix_clk(core_clk),.rst_n(rst_n),.uart_rx(serial_rx),.uart_tx(tx_off),
        .snapshot_core_clk(core_clk),.stats_request_ready(1'b1),.stats_response_valid(1'b0),.stats_response_body(640'd0),
        .snapshot_request_ready(1'b0),.snapshot_stop_ready(1'b0),.snapshot_ack_valid(1'b0),.snapshot_ack_body(352'd0),
        .snapshot_byte_valid(1'b0),.snapshot_byte_data(8'd0),.snapshot_release_valid(1'b0),
        .pixel_valid(1'b0),.frame_start(1'b0),.frame_last(1'b0),.video_abort(1'b0),
        .pixel_x(16'd0),.pixel_y(16'd0),.pixel_rgb(24'd0),.metadata_valid(1'b0),
        .scan_epoch(32'd0),.frame_id(32'd0),.param_id(32'd0),.bank(1'b0),.mode(8'd0),
        .rx_queued(off_q),.rx_rejected(off_r),.rx_busy_drops(off_b),.rx_timeouts(off_t),.signature_dropped(off_d));
    telemetry_uart_link_before #(.WIDTH(16),.HEIGHT(16),.CLOCK_HZ(CLOCK_HZ),.BAUD(BAUD),
        .RX_TIMEOUT_CYCLES(TIMEOUT),.STATS_ENABLE(0),.STATS_LIGHT(1)) before_fix(
        .ctrl_clk(clk),.pix_clk(core_clk),.rst_n(rst_n),.uart_rx(serial_rx),.uart_tx(tx_before),
        .snapshot_core_clk(core_clk),.stats_request_ready(1'b1),.stats_response_valid(1'b0),.stats_response_body(640'd0),
        .snapshot_request_ready(1'b0),.snapshot_stop_ready(1'b0),.snapshot_ack_valid(1'b0),.snapshot_ack_body(352'd0),
        .snapshot_byte_valid(1'b0),.snapshot_byte_data(8'd0),.snapshot_release_valid(1'b0),
        .pixel_valid(1'b0),.frame_start(1'b0),.frame_last(1'b0),.video_abort(1'b0),
        .pixel_x(16'd0),.pixel_y(16'd0),.pixel_rgb(24'd0),.metadata_valid(1'b0),
        .scan_epoch(32'd0),.frame_id(32'd0),.param_id(32'd0),.bank(1'b0),.mode(8'd0),
        .rx_queued(old_q),.rx_rejected(old_r),.rx_busy_drops(old_b),.rx_timeouts(old_t),.signature_dropped(old_d));
    // Original validators tap the actual enabled wrapper's routed streams. Their
    // ready is always1 so this test isolates framing from existing session credit.
    wire arm_valid,stat_valid;wire [31:0] at,an,st,sn,aq,ar,ab,ato,ae,sq,sr,sb,sto,se;
    load_arm_parser #(.BYTE_TIMEOUT_CYCLES(TIMEOUT)) arm_validator(
        .clk(clk),.rst_n(rst_n),.rx_valid(enabled.arm_rx_valid),.rx_error(enabled.arm_rx_error),.rx_data(enabled.arm_rx_data),
        .cmd_valid(arm_valid),.cmd_ready(1'b1),.cmd_ticket(at),.cmd_nonce(an),
        .queued(aq),.rejected(ar),.busy_drops(ab),.timeouts(ato),.framing_errors(ae));
    snapshot_command_parser #(.MAGIC(32'h31544753),.BYTE_TIMEOUT_CYCLES(TIMEOUT)) stats_validator(
        .clk(clk),.rst_n(rst_n),.rx_valid(enabled.stats_rx_valid),.rx_error(enabled.stats_rx_error),.rx_data(enabled.stats_rx_data),
        .cmd_valid(stat_valid),.cmd_ready(1'b1),.cmd_ticket(st),.cmd_nonce(sn),
        .queued(sq),.rejected(sr),.busy_drops(sb),.timeouts(sto),.framing_errors(se));
    integer arm_count=0,stat_count=0,off_edges=0,raw_bytes=0,raw_errors=0,event_file;
    reg [31:0] last_at=0,last_an=0,last_st=0,last_sn=0;
    always @(posedge clk)if(rst_n)begin
        if(arm_valid)begin arm_count=arm_count+1;last_at=at;last_an=an;$fdisplay(event_file,"ARM,%0d,%08h,%08h",$time,at,an);end
        if(stat_valid)begin stat_count=stat_count+1;last_st=st;last_sn=sn;$fdisplay(event_file,"STAT,%0d,%08h,%08h",$time,st,sn);end
        if(enabled.rx_valid)raw_bytes=raw_bytes+1;
        if(enabled.rx_error)raw_errors=raw_errors+1;
    end
    always @(posedge clk)begin
        #1;
        off_edges=off_edges+1;
        if({disabled.arm_rx_valid,disabled.arm_rx_error,disabled.arm_rx_data} !==
           {disabled.rx_valid,disabled.rx_error,disabled.rx_data})$fatal(1,"STATS0 raw RX aliases differ");
        if({tx_off,off_q,off_r,off_b,off_t,off_d} !== {tx_before,old_q,old_r,old_b,old_t,old_d})
            $fatal(1,"STATS0 wrapper public outputs differ from before-fix");
        if(enabled.stats_rx_routing.router.used>4)$fatal(1,"prefix queue overflow");
    end
    `include "packets.vh"
    task automatic uart_byte(input [7:0] b,input bad_stop);
        integer i;begin
            serial_rx=0;repeat(BIT_CYCLES)@(negedge clk);
            for(i=0;i<8;i=i+1)begin serial_rx=b[i];repeat(BIT_CYCLES)@(negedge clk);end
            serial_rx=!bad_stop;repeat(BIT_CYCLES)@(negedge clk);
            if(bad_stop)begin serial_rx=1;repeat(2*BIT_CYCLES)@(negedge clk);end
        end
    endtask
    task automatic uart_packet(input [191:0] p,input integer first,input integer n);
        integer i;begin for(i=first;i<first+n;i=i+1)uart_byte(p[i*8+:8],0);end
    endtask
    task automatic counts(input integer a,input integer s);
        begin if(arm_count!=a || stat_count!=s)$fatal(1,"command count mismatch got ARM%0d STAT%0d expected%0d %0d",arm_count,stat_count,a,s);end
    endtask
    task automatic reset_common;
        begin
            @(negedge clk);rst_n=0;serial_rx=1;repeat(12)@(negedge clk);
            rst_n=1;repeat(12)@(negedge clk);
        end
    endtask
    // Faster-than-UART stress: no replay dead time even at one byte per clock.
    reg burst_valid=0;reg [7:0] burst_data=0;
    wire bav,bae,bsv,bse;wire [7:0] bad,bsd;wire bac,bsc;wire [31:0] bat,ban,bst,bsn;
    integer burst_arms=0,burst_stats=0;
    measurement_rx_router #(.BYTE_TIMEOUT_CYCLES(TIMEOUT)) burst_router(
        .clk(clk),.rst_n(rst_n),.rx_valid(burst_valid),.rx_error(1'b0),.rx_data(burst_data),
        .arm_rx_valid(bav),.arm_rx_error(bae),.arm_rx_data(bad),.stats_rx_valid(bsv),.stats_rx_error(bse),.stats_rx_data(bsd));
    load_arm_parser #(.BYTE_TIMEOUT_CYCLES(TIMEOUT)) burst_arm(
        .clk(clk),.rst_n(rst_n),.rx_valid(bav),.rx_error(bae),.rx_data(bad),
        .cmd_valid(bac),.cmd_ready(1'b1),.cmd_ticket(bat),.cmd_nonce(ban),.queued(),.rejected(),.busy_drops(),.timeouts(),.framing_errors());
    snapshot_command_parser #(.MAGIC(32'h31544753),.BYTE_TIMEOUT_CYCLES(TIMEOUT)) burst_stat(
        .clk(clk),.rst_n(rst_n),.rx_valid(bsv),.rx_error(bse),.rx_data(bsd),
        .cmd_valid(bsc),.cmd_ready(1'b1),.cmd_ticket(bst),.cmd_nonce(bsn),.queued(),.rejected(),.busy_drops(),.timeouts(),.framing_errors());
    always @(posedge clk)if(rst_n)begin
        if(bac)begin burst_arms=burst_arms+1;if(bat!=32'h01020304 || ban!=32'h31544753)$fatal(1,"burst ARM fields");end
        if(bsc)begin burst_stats=burst_stats+1;if(burst_stats==1 && (bst!=32'h31414753 || bsn!=1))$fatal(1,"burst STAT fields");end
        if(burst_router.used>4)$fatal(1,"burst prefix queue overflow");
    end
    task automatic burst_packet(input [191:0] p);
        integer i;begin for(i=0;i<24;i=i+1)begin burst_valid=1;burst_data=p[i*8+:8];@(negedge clk);end end
    endtask
    initial begin
        event_file=$fopen("commands.csv","w");$fdisplay(event_file,"kind,time_ps,ticket,nonce");
        reset_common();
        uart_packet(STAT_A,0,10);reset_common();counts(0,0);
        uart_packet(STAT_A,0,24);uart_packet(ARM_A,0,24);uart_packet(STAT_B,0,24);counts(1,2);
        if(last_at!=32'h01020304 || last_an!=32'h31544753 || last_st!=32'h88776655 || last_sn!=32'h44332211)$fatal(1,"embedded magic changed fields");
        $display("PASS_CONTIGUOUS_UART_EMBEDDED_MAGIC_BOTH_DIRECTIONS");
        uart_packet(BAD_STAT_CRC,0,24);uart_packet(ARM_B,0,24);uart_packet(BAD_ARM_CRC,0,24);uart_packet(STAT_A,0,24);counts(2,3);
        if(ar!=1 || sr!=1)$fatal(1,"bad CRC not rejected by original parsers");
        uart_packet(BAD_STAT_SCHEMA,0,24);uart_packet(BAD_ARM_SCHEMA,0,24);uart_packet(STAT_B,0,24);uart_packet(ARM_A,0,24);counts(3,4);
        if(ar!=2 || sr!=2)$fatal(1,"bad schema not rejected by original parsers");
        $display("PASS_ORIGINAL_PARSER_CRC_AND_SCHEMA_REJECTION");
        uart_packet(STAT_A,0,10);repeat(TIMEOUT+20)@(negedge clk);counts(3,4);
        if(sr!=3)$fatal(1,"truncated stats did not reset validator");
        uart_packet(STAT_A,0,24);uart_packet(ARM_B,0,24);counts(4,5);
        uart_packet(ARM_A,0,12);repeat(TIMEOUT+20)@(negedge clk);counts(4,5);
        if(ar!=3)$fatal(1,"truncated ARM did not reset validator");
        uart_packet(STAT_B,0,24);uart_packet(ARM_A,0,24);counts(5,6);
        uart_byte("S",0);uart_byte("G",0);repeat(TIMEOUT+20)@(negedge clk);
        uart_packet(ARM_B,2,22);counts(5,6);
        uart_packet(STAT_A,0,24);uart_packet(ARM_B,0,24);counts(6,7);
        $display("PASS_TRUNCATED_PARTIAL_MAGIC_TIMEOUT_AND_COMMON_RESET");
        uart_packet(STAT_A,0,4);uart_byte(8'h00,1);
        uart_packet(STAT_B,0,24);uart_packet(ARM_A,0,24);counts(7,8);
        if(raw_errors!=1)$fatal(1,"physical framing error not exercised");
        $display("PASS_PHYSICAL_RX_ERROR_RECOVERY_AND_DISABLED_RAW_ALIAS");
        burst_packet(STAT_A);burst_packet(ARM_A);burst_packet(STAT_B);burst_valid=0;repeat(16)@(negedge clk);
        if(burst_arms!=1 || burst_stats!=2)$fatal(1,"consecutive clock-byte stress lost command");
        $display("PASS_ONE_BYTE_PER_CLOCK_NO_REPLAY_GAP");
        $display("MEASUREMENT_RX_ROUTING_PASS arm=%0d stats=%0d raw_bytes=%0d raw_errors=%0d disabled_edges=%0d",arm_count,stat_count,raw_bytes,raw_errors,off_edges);
        $fclose(event_file);$finish;
    end
    initial begin #(64'd100000000000);$fatal(1,"measurement routing watchdog100ms");end
endmodule
