`timescale 1ns/1ps
module tb_camera_frame_period;
    reg clk=0,rst_n=0,vsync=0;
    always #4 clk=~clk;
    wire [31:0] last_period;
    camera_frame_period dut(.clk(clk),.rst_n(rst_n),.vsync(vsync),.last_period(last_period));
    time edge_time=0,prior_time=0;integer expected;
    task pulse;
        begin
            @(negedge clk);vsync=1;edge_time=$time;
            repeat(3) @(negedge clk);vsync=0;
            repeat(4) @(negedge clk);
            if(prior_time) begin
                expected=(edge_time-prior_time)/8;
                if(last_period!==expected) $fatal(1,"Frame period incorrect actual=%0d expected=%0d",last_period,expected);
            end else if(last_period!==0) $fatal(1,"First edge cannot establish a period");
            prior_time=edge_time;
        end
    endtask
    initial begin
        repeat(5) @(negedge clk);rst_n=1;
        pulse();repeat(17) @(negedge clk);pulse();
        // Core clock continues through long blanking; no camera PCLK needed.
        repeat(1000) @(negedge clk);pulse();
        rst_n=0;repeat(4) @(negedge clk);
        if(last_period!==0) $fatal(1,"Reset retained stale period");
        rst_n=1;prior_time=0;pulse();repeat(48) @(negedge clk);pulse();
        $display("PASS frame period: synchronized frame intervals, long PCLK-independent blanking and reset recovery.");$finish;
    end
    initial begin #20000;$fatal(1,"Period test timeout");end
endmodule
