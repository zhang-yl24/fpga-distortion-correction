`timescale 1ns/1ps
module tb_guarded_command_engine;
    reg clk=0;always #4 clk=~clk;
    reg rst_n=0,byte_valid=0,framing_error=0;
    reg [7:0] byte_data=0;
    reg core_idle=1,fault_active=0,can_grant=1,grant_ready=1;
    reg grant_accepted=0,grant_rejected=0;
    integer feedback_mode=1,grants=0,stops=0;
    wire grant_valid,stop_pulse,reply_event,command_busy;
    wire [31:0] grant_frames,grant_cycles,session_id,accepted_count,rejected_count,duplicate_count,rx_error_count;
    wire [15:0] last_received_seq,last_accepted_seq,requested_frames,lease_ms;
    wire [7:0] last_opcode,last_result;
    guarded_command_engine #(.RX_TIMEOUT_CYCLES(20),.GRANT_TIMEOUT_CYCLES(256)) dut(.*);
    integer accepted=0,rejected=0,duplicates=0,rxerrors=0;
    localparam [31:0] S=32'h12345678,T=32'h87654321;
    always @(posedge clk)begin
        grant_accepted<=grant_valid && feedback_mode==1;
        grant_rejected<=grant_valid && feedback_mode==2;
        if(rst_n && grant_valid)grants=grants+1;
        if(rst_n && stop_pulse)stops=stops+1;
    end
    function [15:0] crc16;
        input [127:0] packet;integer i,j;reg [15:0] c;
        begin c=16'hffff;for(i=2;i<14;i=i+1)begin
            c=c^{packet[i*8+:8],8'b0};
            for(j=0;j<8;j=j+1)c=c[15] ? (c<<1)^16'h1021:c<<1;
        end crc16=c;end
    endfunction
    task send_byte;
        input [7:0] value;
        begin @(negedge clk);byte_valid=1;byte_data=value;
            @(negedge clk);byte_valid=0;end
    endtask
    task command;
        input [7:0] op;input [15:0] seq;input [31:0] session,arg;
        input [7:0] version;input bad_crc;
        reg [127:0] packet;integer i;
        begin
            packet=0;packet[0+:16]=16'h5aa5;packet[16+:8]=version;
            packet[24+:8]=op;packet[32+:16]=seq;packet[48+:32]=session;packet[80+:32]=arg;
            packet[112+:16]=crc16(packet)^(bad_crc ? 16'h0001:16'h0000);
            for(i=0;i<16;i=i+1)send_byte(packet[i*8+:8]);
            repeat(5)@(posedge clk);#1;
        end
    endtask
    task check;
        input [7:0] result;input [15:0] seen,ack;
        begin
            if(last_result!==result || last_received_seq!==seen || last_accepted_seq!==ack ||
                accepted_count!==accepted || rejected_count!==rejected || duplicate_count!==duplicates || rx_error_count!==rxerrors)begin
                $display("EXPECTED result=%h seen=%h ack=%h counts=%0d/%0d/%0d/%0d",result,seen,ack,accepted,rejected,duplicates,rxerrors);
                $display("ACTUAL   result=%h seen=%h ack=%h counts=%0d/%0d/%0d/%0d",last_result,last_received_seq,last_accepted_seq,accepted_count,rejected_count,duplicate_count,rx_error_count);
                $fatal(1,"guarded command state mismatch");
            end
        end
    endtask
    initial begin
        repeat(4)@(posedge clk);@(negedge clk);rst_n=1;
        command(8'h10,1,S,32'd25601,2,0);rejected=rejected+1;check(8'h20,0,0);
        command(8'h0f,1,0,0,2,0);rejected=rejected+1;check(8'h31,0,0);
        core_idle=0;command(8'h0f,1,S,0,2,0);rejected=rejected+1;check(8'h32,0,0);
        core_idle=1;fault_active=1;command(8'h0f,1,S,0,2,0);rejected=rejected+1;check(8'h33,0,0);
        fault_active=0;command(8'h0f,1,S,0,2,0);accepted=accepted+1;check(8'h01,1,1);
        command(8'h0f,1,S,0,2,0);duplicates=duplicates+1;check(8'h02,1,1);
        command(8'h10,2,S,(32'd24000<<8)|3,2,0);accepted=accepted+1;check(8'h01,2,2);
        if(grants!=1 || grant_frames!=3 || grant_cycles!=32'd3000000000)$fatal(1,"grant 32-bit budget or pulse mismatch");
        command(8'h10,2,S,(32'd24000<<8)|3,2,0);duplicates=duplicates+1;check(8'h02,2,2);
        if(grants!=1)$fatal(1,"duplicate renewed grant");
        command(8'h10,2,S,(32'd24000<<8)|2,2,0);rejected=rejected+1;check(8'h23,2,2);
        command(8'h12,1,S,0,2,0);rejected=rejected+1;check(8'h22,2,2);
        command(8'h12,16'h8002,S,0,2,0);rejected=rejected+1;check(8'h22,2,2);
        can_grant=0;command(8'h10,3,S,32'd25601,2,0);rejected=rejected+1;check(8'h34,3,2);
        can_grant=1;command(8'h10,3,S,32'd25601,2,0);duplicates=duplicates+1;check(8'h02,3,2);
        command(8'h10,4,S,32'd25604,2,0);rejected=rejected+1;check(8'h31,4,2);
        feedback_mode=2;command(8'h10,5,S,32'd25601,2,0);rejected=rejected+1;check(8'h35,5,2);
        feedback_mode=1;command(8'h12,6,S,0,2,0);accepted=accepted+1;check(8'h01,6,6);
        command(8'h11,7,S,0,2,0);accepted=accepted+1;check(8'h01,7,7);
        if(grants!=2 || stops!=1)$fatal(1,"STOP/QUERY changed lease grant output");
        command(8'h0f,16'hfffe,T,0,2,0);accepted=accepted+1;check(8'h01,16'hfffe,16'hfffe);
        command(8'h12,16'hffff,T,0,2,0);accepted=accepted+1;check(8'h01,16'hffff,16'hffff);
        command(8'h12,0,T,0,2,0);accepted=accepted+1;check(8'h01,0,0);
        command(8'h12,16'h8000,T,0,2,0);rejected=rejected+1;check(8'h22,0,0);
        command(8'h12,1,S,0,2,0);rejected=rejected+1;check(8'h21,0,0);
        feedback_mode=0;command(8'h10,1,T,32'd25601,2,0);check(8'h00,1,0);
        if(!command_busy || accepted_count!=accepted)$fatal(1,"parsed grant falsely acknowledged");
        command(8'h11,2,T,0,2,0);accepted=accepted+1;rejected=rejected+1;check(8'h01,2,2);
        force grant_accepted=1;@(posedge clk);#1;release grant_accepted;repeat(3)@(posedge clk);#1;
        check(8'h01,2,2);
        command(8'h10,3,T,32'd25601,2,0);check(8'h00,3,2);
        command(8'h12,4,T,0,2,0);rejected=rejected+1;check(8'h37,4,2);
        command(8'h11,5,T,0,2,0);accepted=accepted+1;rejected=rejected+1;check(8'h01,5,5);
        command(8'h10,6,T,32'd25601,2,0);check(8'h00,6,5);
        repeat(270)@(posedge clk);#1;rejected=rejected+1;check(8'h36,6,5);
        command(8'h12,7,T,0,2,0);accepted=accepted+1;check(8'h01,7,7);
        command(8'h12,8,T,0,2,1);rxerrors=rxerrors+1;check(8'h11,7,7);
        command(8'h12,8,T,0,1,0);rxerrors=rxerrors+1;check(8'h10,7,7);
        send_byte(8'ha5);send_byte(8'h5a);send_byte(8'h02);repeat(25)@(posedge clk);#1;
        rxerrors=rxerrors+1;check(8'h13,7,7);
        send_byte(8'ha5);@(negedge clk);framing_error=1;@(negedge clk);framing_error=0;repeat(2)@(posedge clk);#1;
        rxerrors=rxerrors+1;check(8'h12,7,7);
        send_byte(8'h00);send_byte(8'ha5);
        command(8'h12,8,T,0,2,0);accepted=accepted+1;check(8'h01,8,8);
        command(8'h7f,9,T,0,2,0);rejected=rejected+1;check(8'h30,9,8);
        command(8'h7f,9,T,0,2,0);duplicates=duplicates+1;check(8'h02,9,8);
        core_idle=0;command(8'h0f,10,T,0,2,0);rejected=rejected+1;check(8'h32,10,8);
        core_idle=1;command(8'h0f,10,T,0,2,0);duplicates=duplicates+1;check(8'h02,10,8);
        $display("PASS guarded command engine: real RTL CRC/version/timeout/framing, session replay/half-range wrap, rejected-seq consumption, feedback-only ACK, duplicate/STOP/QUERY no renewal, pending stop and 32-bit lease bounds.");
        $finish;
    end
    initial begin #1000000;$fatal(1,"guarded command test watchdog");end
endmodule
