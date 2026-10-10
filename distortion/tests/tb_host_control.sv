`timescale 1ns/1ps
`include "D:/English/FPGA/distortion/build/host_control_sim/counts.vh"
module tb_host_control;
    reg clk=0;always #4 clk=~clk;
    reg rst_n=0,rx=1,key_n=1,allow=1;
    wire byte_valid,byte_error;wire [7:0] byte_data;
    wire cmd_valid,cmd_ready,control_ready;wire [7:0] cmd_opcode;
    wire [15:0] cmd_seq,accepted_seq;wire [31:0] argument,accepted,rejected,duplicates;
    wire auto_mode,cfg_valid;wire [31:0] cfg_phase,requested_phase,command_count;
    wire signed [31:0] cfg_cos,cfg_sin;
    reg [95:0] packets[0:15],golden[0:`HOST_GOLDEN-1];
    uart_rx_control #(.CLOCK_HZ(640000),.BAUD(10000)) receiver(.clk(clk),.rst_n(rst_n),.rx(rx),.valid(byte_valid),.data(byte_data),.framing_error(byte_error));
    rotation_command_parser #(.BYTE_TIMEOUT_CYCLES(1000)) parser(.clk(clk),.rst_n(rst_n),.byte_valid(byte_valid),.byte_data(byte_data),.byte_error(byte_error),
        .cmd_valid(cmd_valid),.cmd_ready(cmd_ready),.cmd_opcode(cmd_opcode),.cmd_seq(cmd_seq),.cmd_argument(argument),.accepted(accepted),.rejected(rejected),.duplicates(duplicates));
    assign cmd_ready=control_ready && allow;
    rotation_host_control #(.DEBOUNCE_CYCLES(4),.LONG_CYCLES(100),.AUTO_CYCLES(12000)) control(
        .clk(clk),.rst_n(rst_n),.key_n(key_n),.cmd_valid(cmd_valid && allow),.cmd_ready(control_ready),.cmd_opcode(cmd_opcode),.cmd_seq(cmd_seq),.cmd_argument(argument),
        .auto_mode(auto_mode),.cfg_valid(cfg_valid),.cfg_phase(cfg_phase),.cfg_cos(cfg_cos),.cfg_sin(cfg_sin),.accepted_seq(accepted_seq),.requested_phase(requested_phase),.command_count(command_count));
    integer j,seen=0;reg held=0;reg [55:0] held_command;
    // Check the ready/valid contract at its actual sampling edge. A command
    // may disappear after the rising edge that accepts it.
    always @(posedge clk) if(rst_n)begin
        if(held && (!cmd_valid || {cmd_opcode,cmd_seq,argument}!==held_command))$fatal(1,"Command changed under backpressure");
        held=cmd_valid && !cmd_ready;held_command={cmd_opcode,cmd_seq,argument};
        if(cfg_valid)begin
            j=-1;for(integer k=0;k<`HOST_GOLDEN;k=k+1)if(golden[k][95:64]===cfg_phase)j=k;
            if(j<0 || {cfg_cos,cfg_sin}!==golden[j][63:0])$fatal(1,"Incorrect/torn arbitrary CORDIC pair phase=%h",cfg_phase);
        end
    end else held=0;
    task send_byte(input [7:0] b,input integer period,input integer bad_stop);
        begin
            @(negedge clk);rx=0;repeat(period)@(negedge clk);
            for(integer k=0;k<8;k=k+1)begin rx=b[k];repeat(period)@(negedge clk);end
            rx=!bad_stop;repeat(period)@(negedge clk);
            rx=1;repeat(70)@(negedge clk);
        end
    endtask
    task send_packet(input [95:0] packet,input integer period);
        begin for(integer k=0;k<12;k=k+1)send_byte(packet[(11-k)*8 +:8],period,0);end
    endtask
    function [95:0] make_packet(input [7:0] ver,op,input [15:0] seq,input [31:0] arg);
        reg [95:0] packet;reg [15:0] c;reg [7:0] b;
        begin
            packet={8'ha5,8'h5a,ver,op,seq[7:0],seq[15:8],arg[7:0],arg[15:8],arg[23:16],arg[31:24],16'd0};c=16'hffff;
            for(integer k=2;k<10;k=k+1)begin b=packet[(11-k)*8 +:8];c=c^{b,8'd0};for(integer m=0;m<8;m=m+1)c=c[15]?(c<<1)^16'h1021:c<<1;end
            packet[15:8]=c[7:0];packet[7:0]=c[15:8];make_packet=packet;
        end
    endfunction
    task verify_command(input integer count,input [31:0] phase);
        begin repeat(80)@(negedge clk);if(command_count!=count || !cfg_valid || cfg_phase!==phase || auto_mode)$fatal(1,"Command not applied count=%0d phase=%h",command_count,cfg_phase);end
    endtask
    integer i,before_reject;reg [31:0] before_phase;
    initial begin
        $readmemh("packets.mem",packets);$readmemh("golden.mem",golden);
        repeat(8)@(negedge clk);rst_n=1;repeat(80)@(negedge clk);
        // Glitched start is rejected at its midpoint.
        rx=0;repeat(5)@(negedge clk);rx=1;repeat(100)@(negedge clk);
        if(command_count)$fatal(1,"Start glitch became a command");
        for(i=0;i<16;i=i+1)begin
            send_packet(packets[i],63+i%3);verify_command(i+1,golden[i][95:64]);
        end
        send_packet(packets[15],64);repeat(80)@(negedge clk);
        if(command_count!=16 || duplicates!=1)$fatal(1,"Duplicate was replayed");
        before_reject=rejected;
        send_packet(make_packet(1,1,16,32'd0),64);
        send_packet(packets[0]^96'h000000000000010000000000,64);
        send_packet(make_packet(2,1,50,32'd0),64);
        send_packet(make_packet(1,2,51,32'd2),64);
        if(rejected!=before_reject+4 || command_count!=16)$fatal(1,"Malformed command changed state");
        // Incomplete packet timeout and low stop/break recovery.
        send_byte(8'ha5,64,0);send_byte(8'h5a,64,0);repeat(1100)@(negedge clk);
        send_byte(8'h55,64,1);repeat(200)@(negedge clk);
        if(command_count!=16)$fatal(1,"UART fault changed command");
        // Hold one packet while another complete packet arrives: no overwrite.
        allow=0;send_packet(make_packet(1,1,100,golden[15][95:64]),64);
        if(!cmd_valid)$fatal(1,"No held command");
        before_reject=rejected;send_packet(make_packet(1,1,101,golden[1][95:64]),64);
        if(rejected!=before_reject+1 || cmd_seq!=100)$fatal(1,"Overflow overwrote a command");
        allow=1;verify_command(17,golden[15][95:64]);
        send_packet(make_packet(1,2,102,1),64);if(!auto_mode)$fatal(1,"Auto not enabled");
        repeat(12100)@(negedge clk);if(cfg_phase==golden[15][95:64])$fatal(1,"Auto not advancing");
        send_packet(make_packet(1,2,103,0),64);if(auto_mode)$fatal(1,"Auto not stopped");
        repeat(80)@(negedge clk);before_phase=cfg_phase;repeat(12100)@(negedge clk);
        if(cfg_phase!=before_phase)$fatal(1,"Stopped auto changed");
        // Reset mid-byte discards the partial packet and recovers cleanly.
        fork begin send_byte(8'ha5,64,0);end begin repeat(200)@(negedge clk);rst_n=0;repeat(8)@(negedge clk);rst_n=1;end join
        repeat(1200)@(negedge clk);held=0;
        send_packet(packets[3],64);verify_command(1,golden[3][95:64]);
        $display("PASS host control: 16 arbitrary angles, exact CORDIC pairs, 63/64/65-cycle UART bits, start glitch, bad stop/break, CRC/version/opcode/sequence rejection, duplicate suppression, partial timeout, command hold/overflow, auto start/stop and mid-byte reset recovery.");$finish;
    end
    initial begin #10000000;$fatal(1,"Host control timeout");end
endmodule
