`timescale 1ns/1ps
// Fixed 128-byte PGSTAT02 record. Freeze all 120 body bytes atomically and
// release ownership only after the 128th byte's complete UART stop bit.
module guarded_status_uart #(
    parameter [31:0] PERIOD_CYCLES=125000000
)(
    input clk,rst_n,request,raw_locked,defer_snapshot,
    input [991:0] payload,
    output reg pending,active,record_started,record_done,
    output reg [31:0] record_sequence,
    output wire byte_valid,input byte_ready,byte_done,output wire [7:0] byte_data
);
    reg [959:0] held;
    reg [31:0] period_count,crc;
    reg [7:0] byte_index;
    reg tail_wait;
    function [31:0] crc_byte;
        input [31:0] previous;input [7:0] value;integer i;reg [31:0] c;
        begin c=previous^{24'b0,value};for(i=0;i<8;i=i+1)
            c=(c>>1)^(c[0]?32'hEDB88320:0);crc_byte=c;end
    endfunction
    assign byte_valid=active && !tail_wait;
    wire [31:0] tail=32'h32305453; // wire bytes "ST02"
    assign byte_data=byte_index<120 ? held[byte_index*8+:8]:
        (byte_index<124 ? (~crc)>>((byte_index-120)*8):tail>>((byte_index-124)*8));
    always @(posedge clk)begin
        if(!rst_n)begin
            pending<=1;active<=0;record_started<=0;record_done<=0;record_sequence<=0;
            held<=0;period_count<=0;crc<=32'hFFFFFFFF;byte_index<=0;tail_wait<=0;
        end else begin
            record_started<=0;record_done<=0;
            if(period_count==PERIOD_CYCLES-1)begin period_count<=0;pending<=1;end
            else period_count<=period_count+1'b1;
            if(request)pending<=1;
            if(!active && pending && !raw_locked && !defer_snapshot && !request)begin
                held<=payload[959:0];active<=1;pending<=0;record_started<=1;
                record_sequence<=record_sequence+1'b1;byte_index<=0;tail_wait<=0;crc<=32'hFFFFFFFF;
            end
            if(byte_valid && byte_ready)begin
                if(byte_index<120)crc<=crc_byte(crc,byte_data);
                if(byte_index==127)tail_wait<=1;
                else byte_index<=byte_index+1'b1;
            end
            if(active && tail_wait && byte_done)begin
                active<=0;tail_wait<=0;record_done<=1;
            end
        end
    end
endmodule
