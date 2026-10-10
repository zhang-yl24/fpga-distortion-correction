`timescale 1ns/1ps
// APB adapter for Logos2 ADC, DCLK 1..100MHz (board uses 27MHz).
// Caller must configure temperature-only scanning, offset correction, and
// ADC clock division. Bias settle and first two conversions are discarded.
module adc_temperature_reader #(
    parameter STARTUP_CYCLES=270000,PERIOD_CYCLES=13500000,
    TIMEOUT_CYCLES=270000,STALE_CYCLES=54000000
)(input clk,rst_n,input adc_done,adc_drdy,input [15:0] adc_do,
    output reg den,secen,output wire dwe,output wire [7:0] daddr,output wire [15:0] di,
    output reg sample_valid,sample_pulse,failed,output reg [7:0] fault,
    output reg [15:0] raw_word,output reg [11:0] code12,
    output reg [31:0] sample_age,conversions,samples);
    localparam IDLE=0,PRE0=1,PRE1=2,WAIT=3,RELEASE=4,FAULT=5;
    reg [2:0] state;
    (* async_reg="true" *) reg [1:0] done_sync;
    reg done_seen;
    reg [31:0] startup,period,timeout,last_epoch;
    reg [1:0] discarded;
    assign dwe=0;assign daddr=8'h40;assign di=0;
    always @(posedge clk) begin
        if(!rst_n) begin
            done_sync<=0;done_seen<=0;startup<=0;discarded<=0;
            state<=IDLE;den<=0;secen<=0;period<=0;timeout<=0;last_epoch<=0;
            sample_valid<=0;sample_pulse<=0;failed<=0;fault<=0;
            raw_word<=0;code12<=0;sample_age<=0;conversions<=0;samples<=0;
        end else begin
            done_sync<={done_sync[0],adc_done};done_seen<=done_sync[1];
            sample_pulse<=0;
            if(startup<STARTUP_CYCLES) startup<=startup+1'b1;
            if(done_sync[1] && !done_seen && startup>=STARTUP_CYCLES) begin
                conversions<=conversions+1'b1;
                if(discarded<2) discarded<=discarded+1'b1;
            end
            if(sample_age<STALE_CYCLES) sample_age<=sample_age+1'b1;
            else sample_valid<=0;
            case(state)
                IDLE: begin
                    if(period<PERIOD_CYCLES) period<=period+1'b1;
                    if(discarded==2 && conversions>2 && conversions!=last_epoch && period>=PERIOD_CYCLES && !adc_drdy) begin
                        den<=1;secen<=0;state<=PRE0;last_epoch<=conversions;timeout<=0;
                    end
                end
                PRE0: state<=PRE1;
                PRE1: begin secen<=1;state<=WAIT;end
                WAIT: begin
                    timeout<=timeout+1'b1;
                    if(adc_drdy) begin
                        den<=0;secen<=0;raw_word<=adc_do;code12<=adc_do[15:4];
                        if(adc_do[15:4]==0) begin failed<=1;fault<=8'h04;sample_valid<=0;state<=FAULT;end
                        else begin
                            sample_valid<=1;sample_pulse<=1;sample_age<=0;samples<=samples+1'b1;
                            period<=0;timeout<=0;state<=RELEASE;
                        end
                    end else if(timeout>=TIMEOUT_CYCLES) begin
                        den<=0;secen<=0;failed<=1;fault<=8'h01;sample_valid<=0;state<=FAULT;
                    end
                end
                RELEASE: begin
                    timeout<=timeout+1'b1;
                    if(!adc_drdy) begin state<=IDLE;timeout<=0;end
                    else if(timeout>=TIMEOUT_CYCLES) begin failed<=1;fault<=8'h02;sample_valid<=0;state<=FAULT;end
                end
                FAULT: begin den<=0;secen<=0;sample_valid<=0;end
                default: begin failed<=1;fault<=8'hff;sample_valid<=0;state<=FAULT;end
            endcase
        end
    end
endmodule
