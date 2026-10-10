`timescale 1ns/1ps
`include "D:/English/FPGA/distortion/build/host_control_sim/counts.vh"
module tb_host_control_concurrent;
    reg clk=0;always #4 clk=~clk;
    reg rst_n=0,key_n=1,cmd_valid=0;wire cmd_ready;
    reg [7:0] opcode=1;reg [15:0] seq=0;reg [31:0] argument=0;
    wire auto_mode,cfg_valid;wire [31:0] phase,requested,count;
    wire [15:0] ack;wire signed [31:0] co,si;
    reg [95:0] golden[0:`HOST_GOLDEN-1];
    rotation_host_control #(.DEBOUNCE_CYCLES(4),.LONG_CYCLES(100),.AUTO_CYCLES(12000)) dut(
        .clk(clk),.rst_n(rst_n),.key_n(key_n),.cmd_valid(cmd_valid),.cmd_ready(cmd_ready),
        .cmd_opcode(opcode),.cmd_seq(seq),.cmd_argument(argument),.auto_mode(auto_mode),
        .cfg_valid(cfg_valid),.cfg_phase(phase),.cfg_cos(co),.cfg_sin(si),
        .accepted_seq(ack),.requested_phase(requested),.command_count(count));
    reg forbid_intermediate=0;reg [31:0] previous_phase=0,allowed_phase;
    always @(negedge clk) if(rst_n && cfg_valid)begin
        integer j;j=-1;
        for(integer k=0;k<`HOST_GOLDEN;k=k+1)if(golden[k][95:64]===phase)j=k;
        if(j<0 || {co,si}!==golden[j][63:0])$fatal(1,"Concurrent command tore CORDIC pair");
        if(forbid_intermediate && phase!=previous_phase && phase!=allowed_phase)$fatal(1,"Obsolete phase published %h",phase);
        previous_phase=phase;
    end
    task request(input [31:0] p);
        begin @(negedge clk);seq=seq+1;opcode=1;argument=p;cmd_valid=1;
            @(negedge clk);cmd_valid=0;end
    endtask
    task settled(input [31:0] p,input integer n);
        begin repeat(90)@(negedge clk);
            if(!cfg_valid || phase!==p || requested!==p || count!=n || ack!=seq || auto_mode)$fatal(1,"Concurrent request not applied");
        end
    endtask
    initial begin
        $readmemh("golden.mem",golden);repeat(8)@(negedge clk);rst_n=1;repeat(90)@(negedge clk);
        allowed_phase=golden[3][95:64];forbid_intermediate=1;
        request(golden[1][95:64]);request(golden[2][95:64]);request(golden[3][95:64]);
        settled(golden[3][95:64],3);forbid_intermediate=0;
        // A new request arrives on exactly the rising edge where an older
        // CORDIC result would otherwise commit.
        request(golden[4][95:64]);
        while(!dut.cordic_valid)@(negedge clk);
        allowed_phase=golden[5][95:64];forbid_intermediate=1;
        seq=seq+1;argument=golden[5][95:64];cmd_valid=1;
        @(negedge clk);cmd_valid=0;settled(golden[5][95:64],5);forbid_intermediate=0;
        request(golden[15][95:64]);settled(golden[15][95:64],6);
        key_n=0;repeat(25)@(negedge clk);key_n=1;repeat(90)@(negedge clk);
        if(phase!==golden[16][95:64] || auto_mode)$fatal(1,"Short KEY0 failed with host controller");
        key_n=0;repeat(130)@(negedge clk);key_n=1;repeat(90)@(negedge clk);
        if(!auto_mode)$fatal(1,"Long KEY0 failed with host controller");
        request(golden[2][95:64]);settled(golden[2][95:64],7);
        $display("PASS concurrent host control: in-flight request coalescing, same-cycle superseded CORDIC result rejection, exact atomic pairs, KEY0 short/long coexistence and host override of auto.");$finish;
    end
    initial begin #100000;$fatal(1,"Concurrent control timeout");end
endmodule
