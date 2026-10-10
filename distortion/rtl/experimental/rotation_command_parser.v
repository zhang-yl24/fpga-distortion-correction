`timescale 1ns/1ps
// A5 5A | version=01 opcode | uint16 seq | uint32 argument | CRC16 LE.
// CRC16/CCITT-FALSE covers the eight version/opcode/seq/argument bytes.
// opcode 01: unsigned modulo-turn phase; opcode 02: auto flag 0 or 1.
// Output is held until accepted. CRC, format, conflicting sequence or overflow
// failures cannot change the currently accepted command.
module rotation_command_parser #(parameter BYTE_TIMEOUT_CYCLES=12500000)(
    input clk,rst_n,byte_valid,input [7:0] byte_data,input byte_error,
    output reg cmd_valid,input cmd_ready,output reg [7:0] cmd_opcode,
    output reg [15:0] cmd_seq,output reg [31:0] cmd_argument,
    output reg [31:0] accepted,rejected,duplicates
);
    localparam SYNC1=0,SYNC2=1,BODY=2;
    reg [1:0] state;reg [3:0] index;
    reg [63:0] payload;reg [15:0] crc;reg [7:0] crc_low;
    reg [31:0] age;reg have_last;
    reg [15:0] last_seq;reg [7:0] last_opcode;reg [31:0] last_argument;
    function [15:0] crc_byte(input [15:0] value,input [7:0] b);
        reg [15:0] c;integer j;
        begin c=value^{b,8'h00};for(j=0;j<8;j=j+1)c=c[15] ? (c<<1)^16'h1021:c<<1;crc_byte=c;end
    endfunction
    wire supported=payload[7:0]==1 && (payload[15:8]==1 ||
        (payload[15:8]==2 && payload[63:32]<=1));
    always @(posedge clk) begin
        if(!rst_n) begin
            state<=SYNC1;index<=0;payload<=0;crc<=16'hffff;crc_low<=0;age<=0;
            cmd_valid<=0;cmd_opcode<=0;cmd_seq<=0;cmd_argument<=0;
            accepted<=0;rejected<=0;duplicates<=0;have_last<=0;last_seq<=0;last_opcode<=0;last_argument<=0;
        end else begin
            if(cmd_valid && cmd_ready) cmd_valid<=0;
            if(state==SYNC1 || byte_valid) age<=0;else age<=age+1'b1;
            if(byte_error) begin state<=SYNC1;age<=0;rejected<=rejected+1'b1;end
            else if(byte_valid) case(state)
                SYNC1: if(byte_data==8'ha5) state<=SYNC2;
                SYNC2: if(byte_data==8'h5a) begin state<=BODY;index<=0;crc<=16'hffff;end
                    else if(byte_data!=8'ha5) state<=SYNC1;
                BODY: begin
                    if(index<8) begin payload[index*8 +:8]<=byte_data;crc<=crc_byte(crc,byte_data);index<=index+1'b1;end
                    else if(index==8) begin crc_low<=byte_data;index<=9;end
                    else begin
                        state<=SYNC1;
                        if({byte_data,crc_low}!=crc || !supported) rejected<=rejected+1'b1;
                        else if(have_last && payload[31:16]==last_seq) begin
                            if(payload[15:8]==last_opcode && payload[63:32]==last_argument) duplicates<=duplicates+1'b1;
                            else rejected<=rejected+1'b1;
                        end else if(cmd_valid && !cmd_ready) rejected<=rejected+1'b1;
                        else begin
                            cmd_valid<=1;cmd_opcode<=payload[15:8];cmd_seq<=payload[31:16];cmd_argument<=payload[63:32];
                            have_last<=1;last_seq<=payload[31:16];last_opcode<=payload[15:8];last_argument<=payload[63:32];
                            accepted<=accepted+1'b1;
                        end
                    end
                end
                default:state<=SYNC1;
            endcase
            else if(state!=SYNC1 && age>=BYTE_TIMEOUT_CYCLES-1) begin state<=SYNC1;age<=0;rejected<=rejected+1'b1;end
        end
    end
endmodule
