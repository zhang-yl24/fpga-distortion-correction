`timescale 1ns/1ps
// Optional byte router AFTER the existing UART receiver. SGA1 is replayed byte
// exact to the unchanged ARM parser; SGR1 never reaches it, even if its payload
// contains SGA1. Hardware UART bytes are >=10*BIT_CYCLES apart; prefix replay4 cycles
// finishes before another physical byte. An impossible faster producer is
// counted/dropped and cannot write video state. No new UART TX owner.
module uart_rotation_router #(parameter integer BYTE_TIMEOUT_CYCLES=2700000)(
    input wire clk,rst_n,rx_valid,rx_error,input wire [7:0] rx_data,
    input wire [31:0] base_param_id,
    output reg arm_rx_valid,arm_rx_error,output reg [7:0] arm_rx_data,
    output reg config_valid,input wire config_ready,output reg [127:0] config_data,
    output reg [31:0] config_queued,config_rejected,config_busy_drops,route_overruns
);
    // SGR1/36 bytes: magic4, version1/opcode1/length2, request_id4,
    // base_param_id4, phase4, cosQ30i4, sinQ30i4, parameter_id4, CRC32LE4.
    // parameter_id=CRC32LE(base_param_id||phase||cos||sin), body CRC covers0..31.
    reg [31:0] search,crc,param_crc,age;
    reg [287:0] packet;
    reg [5:0] count,expected,replay_index;
    reg is_rotation,replaying;
    wire [31:0] next_search={rx_data,search[31:8]};
    wire signed [31:0] packet_cos=$signed(packet[160+:32]);
    wire signed [31:0] packet_sin=$signed(packet[192+:32]);
    wire rotation_schema_ok=packet[32+:8]==1 && packet[40+:8]==1 && packet[48+:16]==36 &&
        packet[64+:32]!=0 && packet[96+:32]==base_param_id && packet[224+:32]==~param_crc &&
        packet_cos>=-32'sd1073741824 && packet_cos<=32'sd1073741824 &&
        packet_sin>=-32'sd1073741824 && packet_sin<=32'sd1073741824 &&
        (packet_cos!=0 || packet_sin!=0);
    function automatic [31:0] crc_byte(input [31:0] c0,input [7:0] b);
        reg [31:0] c;integer k;
        begin c=c0^b;for(k=0;k<8;k=k+1)c=c[0] ? (c>>1)^32'hedb88320:c>>1;crc_byte=c;end
    endfunction
    function automatic [31:0] inc(input [31:0] n);
        begin inc=(&n)?n:n+1'b1;end
    endfunction
    always @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin
            search<=0;crc<=32'hffffffff;param_crc<=32'hffffffff;age<=0;
            packet<=0;count<=0;expected<=0;replay_index<=0;is_rotation<=0;replaying<=0;
            arm_rx_valid<=0;arm_rx_error<=0;arm_rx_data<=0;config_valid<=0;config_data<=0;
            config_queued<=0;config_rejected<=0;config_busy_drops<=0;route_overruns<=0;
        end else begin
            arm_rx_valid<=0;arm_rx_error<=0;
            if(config_valid && config_ready)config_valid<=0;
            if(replaying)begin
                arm_rx_valid<=1;arm_rx_data<=packet[replay_index*8+:8];
                if(replay_index==3)begin replaying<=0;replay_index<=0;end
                else replay_index<=replay_index+1'b1;
                if(rx_valid || rx_error)route_overruns<=inc(route_overruns);
            end else if(rx_error)begin
                // Preserve an ARM framing error when a partial ARM packet was
                // classified, or when idle. Rotation failures stay separate.
                if(count==0 || !is_rotation)arm_rx_error<=1;
                else config_rejected<=inc(config_rejected);
                count<=0;search<=0;age<=0;crc<=32'hffffffff;param_crc<=32'hffffffff;
            end else if(rx_valid)begin
                age<=0;
                if(count==0)begin
                    search<=next_search;
                    if(next_search==32'h31414753 || next_search==32'h31524753)begin
                        packet[31:0]<=next_search;count<=4;search<=0;
                        is_rotation<=next_search==32'h31524753;
                        expected<=next_search==32'h31524753 ? 36:24;
                        if(next_search==32'h31414753)begin replaying<=1;replay_index<=0;end
                        crc<=crc_byte(crc_byte(crc_byte(crc_byte(32'hffffffff,8'h53),8'h47),
                            next_search==32'h31524753 ? 8'h52:8'h41),8'h31);
                        param_crc<=32'hffffffff;
                    end
                end else begin
                    packet[count*8+:8]<=rx_data;
                    if(!is_rotation)begin arm_rx_valid<=1;arm_rx_data<=rx_data;end
                    if(count<expected-4)crc<=crc_byte(crc,rx_data);
                    if(is_rotation && count>=12 && count<28)param_crc<=crc_byte(param_crc,rx_data);
                    if(count==expected-1)begin
                        count<=0;search<=0;
                        if(is_rotation && ({rx_data,packet[256+:24]}!=~crc || !rotation_schema_ok))
                            config_rejected<=inc(config_rejected);
                        else if(is_rotation && config_valid && !config_ready)config_busy_drops<=inc(config_busy_drops);
                        else if(is_rotation)begin
                            config_data<={packet[224+:32],packet[128+:32],packet[160+:32],packet[192+:32]};
                            config_valid<=1;config_queued<=inc(config_queued);
                        end
                    end else count<=count+1'b1;
                end
            end else if(count!=0 || search!=0)begin
                if(age>=BYTE_TIMEOUT_CYCLES-1)begin
                    count<=0;search<=0;age<=0;crc<=32'hffffffff;param_crc<=32'hffffffff;
                    if(count!=0 && is_rotation)config_rejected<=inc(config_rejected);
                    // The unchanged ARM parser owns its original timeout
                    // counter and recovery once the prefix has been replayed.
                end else age<=age+1'b1;
            end
        end
    end
endmodule
