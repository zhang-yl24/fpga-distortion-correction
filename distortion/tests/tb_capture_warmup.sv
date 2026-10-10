`timescale 1ns/1ps
module tb_capture_warmup;
    reg clk=0,rst_n=0,ready=0;wire armed;
    always #4 clk=~clk;
    capture_warmup #(.CLOCK_HZ(1000),.DELAY_MS(12)) dut(.clk(clk),.rst_n(rst_n),.ready(ready),.armed(armed));
    integer i;
    task clock_step;begin @(posedge clk);#1;end endtask
    initial begin
        clock_step();if(armed) $fatal(1,"Armed in reset");
        rst_n=1;repeat(5) begin clock_step();if(armed) $fatal(1,"Armed without readiness");end
        @(negedge clk);ready=1;
        for(i=1;i<=12;i=i+1)begin clock_step();if(armed!==(i==12)) $fatal(1,"Wrong warmup boundary at %0d",i);end
        repeat(30)begin clock_step();if(!armed) $fatal(1,"Counter wrapped after settling");end
        @(negedge clk);ready=0;#1;if(armed) $fatal(1,"Readiness loss did not disarm immediately");clock_step();
        @(negedge clk);ready=1;repeat(6)begin clock_step();if(armed) $fatal(1,"Resumed before complete warmup");end
        @(negedge clk);rst_n=0;clock_step();if(armed) $fatal(1,"Reset did not disarm");
        @(negedge clk);rst_n=1;
        for(i=1;i<=12;i=i+1)begin clock_step();if(armed!==(i==12)) $fatal(1,"Reset recovery warmup boundary");end
        $display("PASS capture warmup: readiness, exact delay, saturation, readiness loss and reset recovery.");$finish;
    end
    initial begin #10000;$fatal(1,"Warmup test timed out");end
endmodule
