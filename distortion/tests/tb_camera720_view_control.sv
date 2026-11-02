`timescale 1ns/1ps
module tb_camera720_view_control;
    localparam integer DEBOUNCE=4;
    reg clk=0;
    always #4 clk=~clk;
    reg rst_n=0,key1_n=0;
    reg fast_rst_n=0,fast_key1_n=0;
    wire corrected_requested,toggle_pulse,fast_corrected,fast_pulse;
    integer toggles=0,fast_toggles=0;
    reg previous_pulse=0,fast_previous_pulse=0;
    reg previous_mode=1,fast_previous_mode=1;
    camera720_view_control #(.DEBOUNCE_CYCLES(DEBOUNCE)) dut(
        .clk(clk),.rst_n(rst_n),.key1_n(key1_n),
        .corrected_requested(corrected_requested),.toggle_pulse(toggle_pulse));
    camera720_view_control #(.DEBOUNCE_CYCLES(1)) fast_dut(
        .clk(clk),.rst_n(fast_rst_n),.key1_n(fast_key1_n),
        .corrected_requested(fast_corrected),.toggle_pulse(fast_pulse));

    // Check every cycle, including transition cycles, rather than only the
    // settled result. Every mode change has exactly one corresponding pulse.
    always @(posedge clk) begin
        #1;
        if(!rst_n) begin
            previous_mode=1;previous_pulse=0;toggles=0;
            if(corrected_requested!==1 || toggle_pulse!==0)
                $fatal(1,"main synchronous reset failed");
        end else begin
            if(toggle_pulse && previous_pulse) $fatal(1,"multi-cycle pulse");
            if(toggle_pulse!==(corrected_requested!=previous_mode))
                $fatal(1,"mode change and pulse disagree");
            if(toggle_pulse) toggles=toggles+1;
            previous_pulse=toggle_pulse;previous_mode=corrected_requested;
        end
        if(!fast_rst_n) begin
            fast_previous_mode=1;fast_previous_pulse=0;fast_toggles=0;
            if(fast_corrected!==1 || fast_pulse!==0) $fatal(1,"fast reset failed");
        end else begin
            if(fast_pulse && fast_previous_pulse) $fatal(1,"fast multi-cycle pulse");
            if(fast_pulse!==(fast_corrected!=fast_previous_mode))
                $fatal(1,"fast mode change and pulse disagree");
            if(fast_pulse) fast_toggles=fast_toggles+1;
            fast_previous_pulse=fast_pulse;fast_previous_mode=fast_corrected;
        end
    end

    task cycles(input integer count);
        repeat(count) begin @(posedge clk);#2;end
    endtask
    task drive(input reg value,input integer count);
        @(negedge clk);key1_n=value;cycles(count);
    endtask
    task expect_main(input integer count,input reg corrected);
        if(toggles!=count || corrected_requested!==corrected)
            $fatal(1,"main count/mode: got %0d/%b expected %0d/%b",toggles,corrected_requested,count,corrected);
    endtask
    task expect_fast(input integer count,input reg corrected);
        if(fast_toggles!=count || fast_corrected!==corrected)
            $fatal(1,"fast count/mode: got %0d/%b expected %0d/%b",fast_toggles,fast_corrected,count,corrected);
    endtask
    initial begin
        cycles(3);
        @(negedge clk);rst_n=1;fast_rst_n=1;
        cycles(20);expect_main(0,1);expect_fast(0,1);
        // Reset while pressed never authorizes a press. Short releases also
        // cannot arm, even after the key has been held for a long time.
        drive(1,2);drive(0,12);expect_main(0,1);
        drive(1,12);expect_main(0,1);
        // Sub-threshold press and repeated contact bounce are ignored.
        drive(0,1);drive(1,3);drive(0,3);drive(1,6);expect_main(0,1);
        // Exactly N synchronized low samples are required. Two synchronizer
        // cycles precede them, including the DEBOUNCE=4 terminal boundary.
        drive(0,DEBOUNCE+1);expect_main(0,1);
        cycles(1);expect_main(1,0);
        cycles(50);expect_main(1,0);
        // Release bounce must not re-arm; a second press during it is ignored.
        drive(1,1);drive(0,8);drive(1,3);drive(0,12);expect_main(1,0);
        drive(1,12);expect_main(1,0);
        drive(0,12);expect_main(2,1);
        drive(1,12);drive(0,12);expect_main(3,0);
        // Reset restores correction and again requires a complete release.
        @(negedge clk);rst_n=0;
        cycles(3);expect_main(0,1);
        @(negedge clk);rst_n=1;
        cycles(15);expect_main(0,1);
        drive(1,12);drive(0,12);expect_main(1,0);

        // The N=1 specialization retains the two-flop input latency, handles
        // a held reset key, and produces exactly one event per release/press.
        @(negedge clk);fast_key1_n=1;
        cycles(3);expect_fast(0,1);
        @(negedge clk);fast_key1_n=0;
        cycles(2);expect_fast(0,1);
        cycles(1);expect_fast(1,0);
        cycles(30);expect_fast(1,0);
        @(negedge clk);fast_key1_n=1;
        cycles(3);
        @(negedge clk);fast_key1_n=0;
        cycles(3);expect_fast(2,1);
        @(negedge clk);fast_rst_n=0;
        cycles(2);
        @(negedge clk);fast_rst_n=1;
        cycles(10);expect_fast(0,1);
        $display("CAMERA720_VIEW_CONTROL_PASS debounce=4,1 bounce hold reset pulse boundary");
        $finish;
    end
    initial begin #100000;$fatal(1,"test timeout");end
endmodule
