`timescale 1ns/1ps
// One fixed 24-byte command; validated output is held. Full slot drops later
// complete valid commands and counts them. No RX or video backpressure output.
module load_arm_parser #(
    parameter integer BYTE_TIMEOUT_CYCLES=2700000
)(
    input wire clk,rst_n,rx_valid,rx_error,input wire [7:0] rx_data,
    output reg cmd_valid,input wire cmd_ready,output reg [31:0] cmd_ticket,cmd_nonce,
    output reg [31:0] queued,rejected,busy_drops,timeouts,framing_errors
);
    `include "reuse/crc_byte.vh"
    (* PAP_ASYNC_REG=1 *) reg [1:0] release_sync=0;
    reg [4:0] index;
    reg [159:0] body;
    reg [23:0] received_crc;
    reg [31:0] crc,age;
    function [31:0] inc(input [31:0] value);
        begin inc=(&value)?value:value+1'b1;end
    endfunction
    function [7:0] magic(input [1:0] i);
        begin case(i) 0:magic="S";1:magic="G";2:magic="A";default:magic="1";endcase end
    endfunction
    wire schema_ok=body[32+:8]==1 && body[40+:8]==1 && body[48+:16]==24 &&
        body[64+:32]!=0 && body[96+:32]!=0 && body[128+:32]==0;
    always @(posedge clk or negedge rst_n)
        if(!rst_n)release_sync<=0;else release_sync<={release_sync[0],1'b1};
    always @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin
            index<=0;body<=0;received_crc<=0;crc<=32'hffffffff;age<=0;
            cmd_valid<=0;cmd_ticket<=0;cmd_nonce<=0;queued<=0;rejected<=0;busy_drops<=0;timeouts<=0;framing_errors<=0;
        end else if(!release_sync[1])begin
            index<=0;body<=0;received_crc<=0;crc<=32'hffffffff;age<=0;
            cmd_valid<=0;cmd_ticket<=0;cmd_nonce<=0;queued<=0;rejected<=0;busy_drops<=0;timeouts<=0;framing_errors<=0;
        end else begin
            if(cmd_valid && cmd_ready)cmd_valid<=0;
            if(rx_error)begin
                index<=0;age<=0;crc<=32'hffffffff;
                framing_errors<=inc(framing_errors);rejected<=inc(rejected);
            end else if(rx_valid)begin
                age<=0;
                if(index<4)begin
                    if(rx_data==magic(index[1:0]))begin
                        body[index*8+:8]<=rx_data;
                        crc<=crc_byte(index==0?32'hffffffff:crc,rx_data);
                        index<=index+1'b1;
                    end else if(rx_data=="S")begin
                        body[0+:8]<=rx_data;crc<=crc_byte(32'hffffffff,rx_data);index<=1;
                    end else begin index<=0;crc<=32'hffffffff;end
                end else if(index<20)begin
                    body[index*8+:8]<=rx_data;crc<=crc_byte(crc,rx_data);index<=index+1'b1;
                end else if(index<23)begin
                    received_crc[(index-20)*8+:8]<=rx_data;index<=index+1'b1;
                end else begin
                    index<=0;crc<=32'hffffffff;
                    if({rx_data,received_crc}!=~crc || !schema_ok)rejected<=inc(rejected);
                    else if(cmd_valid && !cmd_ready)busy_drops<=inc(busy_drops);
                    else begin
                        cmd_valid<=1;cmd_ticket<=body[64+:32];cmd_nonce<=body[96+:32];queued<=inc(queued);
                    end
                end
            end else if(index!=0)begin
                if(age>=BYTE_TIMEOUT_CYCLES-1)begin
                    index<=0;age<=0;crc<=32'hffffffff;timeouts<=inc(timeouts);rejected<=inc(rejected);
                end else age<=age+1'b1;
            end else age<=0;
        end
    end
endmodule
