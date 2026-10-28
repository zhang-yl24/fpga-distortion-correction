`timescale 1ns/1ps
// Actual six-pin board top, actual SCCB and 8N1 UART; no vendor stubs or forced bus errors.
module tb_cam1_transaction_probe_uart;
    reg clk=0;always #18.519 clk=~clk;
    tri1 cam_rst_n,cam_scl,cam_sda;wire uart_txd,led0;
    reg slave_low=0,slave_clock_low=0;
    assign cam_sda=slave_low ? 1'b0:1'bz;
    assign cam_scl=slave_clock_low ? 1'b0:1'bz;
    cam1_transaction_probe #(.STATUS_PERIOD_CYCLES(20000)) dut(.clk_27m(clk),.*);
    defparam dut.camera.RESET_CYCLES=8,dut.camera.WAIT_CYCLES=12,dut.camera.MS_CYCLES=2;
    integer case_id=0,writes=0,stream_file=0,success_seen=0,nack_seen=0,packet_count=0;
    integer expected_seq=1,changed_uptime=0;
    reg [7:0] registers[0:65535],packet[0:63];
    reg pause_rx=1,rx_paused=0;
    reg [447:0] held_snapshot;reg prior_active=0;
    always @(negedge clk)begin
        if(dut.rst_n && dut.packet_active && prior_active && dut.snapshot!==held_snapshot)
            $fatal(1,"Snapshot changed before final physical UART stop-bit byte_done");
        if(dut.packet_active)held_snapshot=dut.snapshot;
        prior_active=dut.packet_active;
    end
    task automatic get_start;
        begin do @(negedge cam_sda); while(cam_scl!==1); end
    endtask
    task automatic get_byte(output reg [7:0] value,input bit ack);
        begin
            value=0;
            repeat(8)begin @(posedge cam_scl);value={value[6:0],cam_sda};end
            @(negedge cam_scl);slave_low=ack;
            @(posedge cam_scl);@(negedge cam_scl);slave_low=0;
        end
    endtask
    task automatic expect_byte(input [7:0] expected,input bit ack);
        reg [7:0] value;
        begin get_byte(value,ack);if(value!==expected)$fatal(1,"Case%0d wire byte %h vs %h",case_id,value,expected);end
    endtask
    task automatic reply(input [7:0] value);
        begin
            for(integer i=7;i>=0;i=i-1)begin
                slave_low=!value[i];@(posedge cam_scl);@(negedge cam_scl);
            end
            slave_low=0;@(posedge cam_scl);
            if(cam_sda!==1)$fatal(1,"Master must terminate read with NACK");
            @(negedge cam_scl);
        end
    endtask
    // phase1: first 0x78 address NACK; phase2: repeated-start 0x79 NACK.
    task automatic register_read(input [15:0] address,input [7:0] value,input integer phase);
        begin
            get_start();expect_byte(8'h78,phase!=1);
            if(phase!=1)begin
                expect_byte(address[15:8],1);expect_byte(address[7:0],1);
                get_start();expect_byte(8'h79,phase!=2);
                if(phase!=2)reply(value);
            end
        end
    endtask
    task automatic register_write(input bit data_ack,input bit bad_device,input integer read_phase,input bit bad_value);
        reg [7:0] hi,lo,value;
        begin
            get_start();expect_byte(8'h78,!bad_device);
            if(!bad_device)begin
                get_byte(hi,1);get_byte(lo,1);get_byte(value,data_ack);
                // Sensor model accepts the byte even when its final Don't-Care
                // level is high; host must still verify it, as in the old policy.
                registers[{hi,lo}]=value;writes=writes+1;
                if(!data_ack || dut.camera.checkable_write({hi,lo}))
                    register_read({hi,lo},bad_value ? 8'h00:value,read_phase);
            end
        end
    endtask
    task automatic prefix;
        begin register_read(16'h300a,8'h56,0);register_read(16'h300b,8'h40,0);
            repeat(262)register_write(1,0,0,0);end
    endtask
    task automatic verify_seven;
        begin register_read(16'h3808,8'h02,0);register_read(16'h3809,8'h80,0);
            register_read(16'h380a,8'h01,0);register_read(16'h380b,8'he0,0);
            register_read(16'h4300,8'h6f,0);register_read(16'h501f,8'h01,0);
            register_read(16'h4740,8'h23,0);end
    endtask
    task automatic uart_byte(output reg [7:0] value);
        begin
            @(negedge uart_txd);repeat(14)@(posedge clk);#1;
            if(uart_txd!==0)$fatal(1,"UART start bit");
            for(integer bitno=0;bitno<8;bitno=bitno+1)begin repeat(29)@(posedge clk);#1;value[bitno]=uart_txd;end
            repeat(29)@(posedge clk);#1;if(uart_txd!==1)$fatal(1,"UART stop bit");
        end
    endtask
    function [31:0] u32(input integer n);begin u32={packet[n+3],packet[n+2],packet[n+1],packet[n]};end endfunction
    function [15:0] u16(input integer n);begin u16={packet[n+1],packet[n]};end endfunction
    function [31:0] crc_byte(input [31:0] previous,input [7:0] value);
        reg [31:0] c;begin c=previous^value;for(integer n=0;n<8;n=n+1)c=(c>>1)^(c[0]?32'hedb88320:0);crc_byte=c;end
    endfunction
    reg [31:0] check_crc;
    initial forever begin
        if(pause_rx)begin rx_paused=1;wait(!pause_rx);rx_paused=0;end
        for(integer n=0;n<64;n=n+1)begin uart_byte(packet[n]);$fwrite(stream_file,"%c",packet[n]);end
        if({packet[0],packet[1],packet[2],packet[3],packet[4],packet[5],packet[6],packet[7]}!=="PGCAMD01" ||
           packet[8]!=1 || packet[9]!=64 || packet[10]!=1 || packet[11]!=0)$fatal(1,"PGCAMD01 identity/header");
        check_crc=32'hffffffff;for(integer n=0;n<56;n=n+1)check_crc=crc_byte(check_crc,packet[n]);
        if(u32(56)!==~check_crc || {packet[60],packet[61],packet[62],packet[63]}!=="CD01")$fatal(1,"Actual UART packet CRC/tail");
        for(integer n=50;n<56;n=n+1)if(packet[n]!=0)$fatal(1,"Nonzero reserved byte");
        if(u16(37)!=16'h7ff0 || u16(39)!=68 || u32(45)!=expected_seq)$fatal(1,"Snapshot parameter/sequence");
        expected_seq=expected_seq+1;packet_count=packet_count+1;
        if(dut.uptime_ms!=u32(41))changed_uptime=changed_uptime+1;
        if(!dut.packet_active || dut.byte_index!=63 || !dut.waiting_done)$fatal(1,"Packet ownership released before final stop-bit completes");
        if(case_id==0 && packet[27][0])begin
            if(packet[27][1] || packet[14]!=0 || u16(12)!=16'h5640 || u16(18)!=264 || u16(20)!=0 ||
               packet[15]!=8'hf3 || packet[24]!=0 || packet[25]!=0 || packet[26]!=8'hf0 ||
               packet[27]!=9 || packet[28]!=0 || packet[29]!=0 || packet[30]!=0 || packet[31]!=0)
                $fatal(1,"Successful original init fields changed");
            success_seen=success_seen+1;
        end
        if(case_id==1 && packet[27][2])begin
            if(packet[27]!=14 || packet[14]!=8'h61 || u16(12)!=16'h5640 || u16(16)!=16'h3018 ||
               u16(18)!=262 || u16(20)!=0 || packet[15]!=8'h3f || packet[23]!=8'hf0 ||
               packet[24]!=4 || packet[25]!=1 || packet[28]!=7 || packet[29]!=7 || packet[30]!=7 ||
               packet[31]!=3 || u16(32)!=0 || packet[34]!=8'h56 || packet[35]!=8'h40 || packet[36]!=8'hf0)
                $fatal(1,"Read1/write4/pending/invalid-read/probe fields conflated");
            nack_seen=nack_seen+1;
        end
        wait(dut.serial_done);@(posedge clk);#1;
        if(dut.packet_active)$fatal(1,"Packet not released at final byte_done");
    end
    task automatic reset_case(input integer value);
        begin
            force dut.power_count=20'h00000;slave_low=0;slave_clock_low=0;case_id=value;
            writes=0;expected_seq=1;repeat(8)@(negedge clk);
            force dut.power_count=20'hfffff;pause_rx=0;
        end
    endtask
    initial begin
        stream_file=$fopen("pgcamd01-success-wire.bin","wb");#100;reset_case(0);
        prefix();register_write(1,0,0,0);verify_seven();register_write(1,0,0,0);verify_seven();
        wait(success_seen>=2);pause_rx=1;wait(rx_paused);$fclose(stream_file);
        stream_file=$fopen("pgcamd01-read-nack-wire.bin","wb");reset_case(1);
        prefix();register_write(0,0,1,0); // Final data high, then read-address NACK.
        register_read(16'h300a,8'h56,0);register_read(16'h300b,8'h40,0);register_read(16'h3018,8'hf0,0);
        wait(nack_seen>=2);pause_rx=1;wait(rx_paused);$fclose(stream_file);
        if(changed_uptime==0)$fatal(1,"No changing live uptime observed while a frozen packet was transmitted");
        $display("PASS actual cam1_transaction_probe UART: complete_original_success and write4_read1_pending61, all64 byte CRC/fields, immutable snapshots, live changes, final physical stop-bit ownership; packets=%0d.",packet_count);$finish;
    end
    initial begin #1500000000;$fatal(1,"Actual diagnostic UART regression timeout case%0d success%0d nack%0d",case_id,success_seen,nack_seen);end
endmodule
