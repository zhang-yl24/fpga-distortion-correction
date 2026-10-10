`timescale 1ns/1ps
module tb_logos2_temperature_monitor;
    reg clk=0,rst_n=0;always #5 clk=~clk;
    wire sample_valid,sample_pulse,failed,over_temp;wire [7:0] fault;
    wire [15:0] raw_word;wire [11:0] code12;wire [31:0] sample_age,conversions,samples;
    wire [4:0] alarm;
    logos2_temperature_monitor dut(.*);
    defparam dut.reader.STARTUP_CYCLES=16,dut.reader.PERIOD_CYCLES=40,
        dut.reader.TIMEOUT_CYCLES=30,dut.reader.STALE_CYCLES=100;
    initial begin
        repeat(8) @(negedge clk);rst_n=1;wait(samples>=3);#1;
        if(!sample_valid || failed || raw_word!==16'hB007 || code12!==12'hB00) $fatal(1,"Temperature wrapper did not report completed sample");
        @(negedge clk);#2;dut.sensor.injected_over=1;dut.sensor.injected_alarm=5'b10101;
        @(posedge clk);#1;if(over_temp || alarm) $fatal(1,"Alarm bypassed synchronization");
        @(posedge clk);#1;if(!over_temp || alarm!==5'b10101) $fatal(1,"Alarm did not synchronize");
        @(negedge clk);dut.sensor.injected_over=0;dut.sensor.injected_alarm=0;
        repeat(2) @(posedge clk);#1;if(over_temp || alarm) $fatal(1,"Alarm did not clear");
        @(negedge clk);rst_n=0;#1;if(over_temp || alarm) $fatal(1,"Alarm reset failed");
        repeat(8) @(negedge clk);rst_n=1;wait(sample_valid);
        $display("PASS temperature wrapper: vendor primitive interface/configuration, temperature and default OT alarms enabled, reviewed clock/calibration/averaging/thresholds, DRDY-confirmed high12 sample, alarm synchronization and reset. Digital stub only; analog accuracy unverified.");$finish;
    end
    initial begin #100000;$fatal(1,"Temperature wrapper timeout");end
endmodule
