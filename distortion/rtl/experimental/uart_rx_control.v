`timescale 1ns/1ps
// 8N1 receiver in the core clock domain; no multi-bit clock crossing.
// Input pin crosses only through the two-flop synchronizer.
module uart_rx_control #(parameter CLOCK_HZ=125000000,BAUD=115200)(
    input clk,rst_n,rx,output reg valid,output reg [7:0] data,output reg framing_error
);
    localparam BIT_CYCLES=(CLOCK_HZ+BAUD/2)/BAUD;
    localparam IDLE=0,START=1,DATA=2,STOP=3,BREAK=4;
    (* async_reg="true" *) reg [1:0] rx_sync=3;
    reg [2:0] state;reg [31:0] count;reg [2:0] bit_index;reg [7:0] shift;
    always @(posedge clk or negedge rst_n)
        if(!rst_n) rx_sync<=3;else rx_sync<={rx_sync[0],rx};
    always @(posedge clk) begin
        if(!rst_n) begin state<=IDLE;count<=0;bit_index<=0;shift<=0;valid<=0;data<=0;framing_error<=0;end
        else begin
            valid<=0;framing_error<=0;
            case(state)
                IDLE: if(!rx_sync[1]) begin count<=0;state<=START;end
                START: if(count==BIT_CYCLES/2-1) begin
                    count<=0;
                    if(!rx_sync[1]) begin bit_index<=0;state<=DATA;end
                    else state<=IDLE;
                end else count<=count+1'b1;
                DATA: if(count==BIT_CYCLES-1) begin
                    count<=0;shift[bit_index]<=rx_sync[1];
                    if(bit_index==7) state<=STOP;else bit_index<=bit_index+1'b1;
                end else count<=count+1'b1;
                STOP: if(count==BIT_CYCLES-1) begin
                    count<=0;
                    if(rx_sync[1]) begin data<=shift;valid<=1;state<=IDLE;end
                    else begin framing_error<=1;state<=BREAK;end
                end else count<=count+1'b1;
                BREAK: if(!rx_sync[1]) count<=0;
                    else if(count==BIT_CYCLES-1) begin count<=0;state<=IDLE;end
                    else count<=count+1'b1;
                default:state<=IDLE;
            endcase
        end
    end
endmodule
