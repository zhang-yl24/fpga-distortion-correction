`timescale 1ns/1ps
// Official GTP_ADC_E2 temperature-only continuous scan; internal analog pins
// need no external wiring. Configuration is isolated from baseline targets.
module logos2_temperature_monitor(input clk,rst_n,
    output sample_valid,sample_pulse,failed,output [7:0] fault,
    output [15:0] raw_word,output [11:0] code12,
    output [31:0] sample_age,conversions,samples,
    output over_temp,output [4:0] alarm);
    wire den,secen,dwe,drdy,logic_done;
    wire raw_over_temp;wire [4:0] raw_alarm;
    (* async_reg="true" *) reg [5:0] alarm_meta=0,alarm_sync=0;
    always @(posedge clk or negedge rst_n)
        if(!rst_n) begin alarm_meta<=0;alarm_sync<=0;end
        else begin alarm_meta<={raw_over_temp,raw_alarm};alarm_sync<=alarm_meta;end
    assign over_temp=alarm_sync[5];assign alarm=alarm_sync[4:0];
    wire [7:0] daddr;wire [15:0] di,adc_do;
    GTP_ADC_E2 #(
        .CREG_00H(16'h1003), // Sequence scan, temperature alarm and default OT enable.
        .CREG_01H(16'h5020), // Offset calibration, 64-sample average, divide by34.
        .CREG_02H(16'h0008), // Continuous mode, internal reference/oscillator.
        .CREG_03H(16'h0004),.CREG_04H(16'h0000),.CREG_05H(16'h0000),.CREG_06H(16'h0000),
        .CREG_07H(16'h0004),.CREG_08H(16'h0000),.CREG_0AH(16'h0000),.CREG_0CH(16'h0000),.CREG_0EH(16'h0000),
        .CREG_20H(16'h0B7A),.CREG_21H(16'h0AAD), // Diagnostic approx85C upper/60C lower.
        .CREG_22H(16'h0000),.CREG_23H(16'h0000),.CREG_24H(16'h0000),.CREG_25H(16'h0000),
        .CREG_26H(16'h0000),.CREG_27H(16'h0000),.CREG_28H(16'h0000),.CREG_29H(16'h0000),
        .CREG_2AH(16'h0CC2),.CREG_2BH(16'h0A5B),.CREG_31H(16'h0000)
    ) sensor(.VA(2'b0),.VAUX(32'b0),.DCLK(clk),.RST_N(rst_n),.DEN(den),.SECEN(secen),
        .DWE(dwe),.DADDR(daddr),.DI(di),.CONVST(1'b0),.LOADSC_N(1'b1),
        .DO(adc_do),.DRDY(drdy),.LOGIC_DONE_A(logic_done),.LOGIC_DONE_B(),.ADC_CLK_OUT(),
        .DMODIFIED(),.OVER_TEMP(raw_over_temp),.ALARM(raw_alarm));
    adc_temperature_reader reader(.clk(clk),.rst_n(rst_n),.adc_done(logic_done),.adc_drdy(drdy),.adc_do(adc_do),
        .den(den),.secen(secen),.dwe(dwe),.daddr(daddr),.di(di),.sample_valid(sample_valid),.sample_pulse(sample_pulse),
        .failed(failed),.fault(fault),.raw_word(raw_word),.code12(code12),.sample_age(sample_age),.conversions(conversions),.samples(samples));
endmodule
