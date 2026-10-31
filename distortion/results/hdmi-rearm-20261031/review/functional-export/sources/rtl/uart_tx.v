`timescale 1ns/1ps
module uart_tx #(parameter CLOCK_HZ=27000000, parameter BAUD=115200)(
    input clk, input rst_n, input start, input [7:0] data,
    output reg tx, output reg busy, output reg done
);
    localparam BIT_CYCLES=(CLOCK_HZ+BAUD/2)/BAUD;
    reg [31:0] count;
    reg [3:0] bit_index;
    reg [9:0] shift;
    always @(posedge clk) begin
        if(!rst_n) begin tx<=1; busy<=0; done<=0; count<=0; bit_index<=0; shift<=10'h3ff; end
        else begin
            done<=0;
            if(!busy) begin
                if(start) begin
                    shift<={1'b1,data,1'b0}; tx<=0; busy<=1; count<=0; bit_index<=0;
                end
            end else if(count==BIT_CYCLES-1) begin
                count<=0;
                if(bit_index==9) begin busy<=0; done<=1; tx<=1; end
                else begin shift<={1'b1,shift[9:1]}; tx<=shift[1]; bit_index<=bit_index+1; end
            end else count<=count+1;
        end
    end
endmodule
