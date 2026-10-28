`timescale 1ns/1ps
// Low-activity diagnostic only: 27MHz clock, eight LEDs and UART TX.
// No DDR, camera or HDMI ports. Temperature ADC state is observed, not assumed
// healthy. GTP_ADC status is distinct from JTAG mode-3 over_temp status bits.
module thermal_idle(input clk_27m,output [7:0] led,output uart_txd);
    reg [19:0] power_count=0;
    wire rst_n=&power_count;
    always @(posedge clk_27m)if(!rst_n)power_count<=power_count+1'b1;
    reg [23:0] heart_count=0;reg heart=0;
    always @(posedge clk_27m)begin
        if(!rst_n)begin heart_count<=0;heart<=0;end
        else if(heart_count==13499999)begin heart_count<=0;heart<=!heart;end
        else heart_count<=heart_count+1'b1;
    end
    wire temp_valid,temp_pulse,temp_failed,temp_over;wire [7:0] temp_fault;
    wire [4:0] temp_alarm;wire [15:0] temp_raw;wire [11:0] temp_code;
    wire [31:0] temp_age,temp_conversions,temp_samples;
    logos2_temperature_monitor temperature(.clk(clk_27m),.rst_n(rst_n),
        .sample_valid(temp_valid),.sample_pulse(temp_pulse),.failed(temp_failed),.fault(temp_fault),
        .raw_word(temp_raw),.code12(temp_code),.sample_age(temp_age),.conversions(temp_conversions),
        .samples(temp_samples),.over_temp(temp_over),.alarm(temp_alarm));
    wire byte_valid,byte_ready,byte_done,serial_busy;wire [7:0] byte_data;
    thermal_idle_telemetry telemetry(.clk(clk_27m),.rst_n(rst_n),
        .sample_valid(temp_valid),.failed(temp_failed),.fault(temp_fault),
        .raw_word(temp_raw),.code12(temp_code),.sample_age(temp_age),.samples(temp_samples),
        .conversions(temp_conversions),.over_temp(temp_over),.alarm(temp_alarm),
        .byte_valid(byte_valid),.byte_ready(byte_ready),.byte_done(byte_done),.byte_data(byte_data),
        .record_started(),.record_done(),.record_sequence());
    uart_tx #(.CLOCK_HZ(27000000),.BAUD(921600)) serial(.clk(clk_27m),.rst_n(rst_n),
        .start(byte_valid && byte_ready),.data(byte_data),.tx(uart_txd),.busy(serial_busy),.done(byte_done));
    assign byte_ready=!serial_busy;
    assign led={temp_over,temp_failed,temp_valid,|temp_alarm,3'b000,heart};
endmodule
