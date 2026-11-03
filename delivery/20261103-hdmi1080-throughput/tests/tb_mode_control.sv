`timescale 1ns/1ps
module tb_mode_control;
    reg clk=0,rst_n=0,commit_pulse=0,failed=0;
    always #4 clk=~clk;
    wire raw,corrected,demo;
    frame_ab_control #(.MODE(0),.HOLD_CYCLES(8)) raw_dut(clk,rst_n,commit_pulse,failed,raw);
    frame_ab_control #(.MODE(1),.HOLD_CYCLES(8)) corrected_dut(clk,rst_n,commit_pulse,failed,corrected);
    frame_ab_control #(.MODE(2),.HOLD_CYCLES(8)) demo_dut(clk,rst_n,commit_pulse,failed,demo);
    integer cycle,elapsed=0;
    reg expected_demo=0;
    always @(posedge clk)begin
        if(!rst_n)begin elapsed=0;expected_demo=0;end
        else if(!failed)begin
            if(elapsed==7)begin
                if(commit_pulse)begin elapsed=0;expected_demo=~expected_demo;end
            end else elapsed=elapsed+1;
        end
        #1;
        if(raw!==0 || corrected!==1 || demo!==expected_demo)$fatal(1,"mode/control mismatch");
    end
    initial begin
        repeat(3)@(negedge clk);
        rst_n=1;
        for(cycle=0;cycle<160;cycle=cycle+1)begin
            @(negedge clk);
            commit_pulse=(cycle%3)==0;
            failed=cycle>=60 && cycle<85;
            rst_n=cycle!=110;
        end
        @(negedge clk);
        $display("PASS MODE_CONTROL fixed_raw fixed_corrected demo fault reset");
        $finish;
    end
endmodule
