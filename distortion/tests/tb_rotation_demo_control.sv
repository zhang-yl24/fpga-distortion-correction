`timescale 1ns/1ps
module tb_rotation_demo_control;
    reg clk=0,rst_n=0,key_n=1;always #4 clk=~clk;
    wire auto_mode,cfg_valid;wire [31:0] cfg_phase;wire signed [31:0] cfg_cos,cfg_sin;
    rotation_demo_control #(.DEBOUNCE_CYCLES(4),.LONG_CYCLES(80),.AUTO_CYCLES(70)) dut(.*);
    reg [95:0] vectors[0:11];integer i,j,mask=0,commits=0;reg [31:0] before_phase;
    always @(negedge clk) if(cfg_valid) begin
        j=-1;for(integer k=0;k<12;k=k+1) if(cfg_phase===vectors[k][95:64]) j=k;
        if(j<0 || {cfg_cos,cfg_sin}!==vectors[j][63:0]) $fatal(1,"Torn or incorrect parameter commit");
        mask=mask|(1<<j);
    end
    task short_press;
        begin @(negedge clk);key_n=0;repeat(13) @(negedge clk);key_n=1;repeat(50) @(negedge clk);end
    endtask
    task long_press;
        begin @(negedge clk);key_n=0;repeat(100) @(negedge clk);key_n=1;repeat(12) @(negedge clk);end
    endtask
    initial begin
        $readmemh("vectors.mem",vectors);repeat(8) @(negedge clk);rst_n=1;
        wait(cfg_valid);repeat(3) @(negedge clk);
        if(cfg_phase!=0 || auto_mode) $fatal(1,"Invalid reset default");
        key_n=0;repeat(2) @(negedge clk);key_n=1;repeat(50) @(negedge clk);
        if(cfg_phase!=0) $fatal(1,"Bounce became a press");
        for(i=1;i<=12;i=i+1) begin
            short_press();
            if(cfg_phase!==vectors[i%12][95:64]) $fatal(1,"Missing short press or wrap i=%0d got=%h expected=%h desired=%0d hold=%0d",i,cfg_phase,vectors[i%12][95:64],dut.desired_index,dut.hold_count);
        end
        if(mask!=4095) $fatal(1,"Incomplete full-circle coverage");
        before_phase=cfg_phase;long_press();
        if(!auto_mode || cfg_phase!==before_phase) $fatal(1,"Long press also generated short press");
        repeat(210) @(negedge clk);
        if(cfg_phase===before_phase) $fatal(1,"auto_mode rotation did not advance");
        long_press();if(auto_mode) $fatal(1,"auto_mode mode did not stop");
        repeat(40) @(negedge clk);before_phase=cfg_phase;repeat(180) @(negedge clk);
        if(cfg_phase!==before_phase) $fatal(1,"Stopped auto_mode mode changed parameters");
        rst_n=0;repeat(8) @(negedge clk);rst_n=1;wait(cfg_valid);
        if(cfg_phase!=0 || auto_mode) $fatal(1,"Reset recovery failed");
        $display("PASS rotation control: deglitched active-low key, twelve exact CORDIC angle pairs, 360-degree wrap, long/short distinction, auto_mode start/stop and reset recovery.");$finish;
    end
    initial begin #100000;$fatal(1,"Rotation control timeout");end
endmodule
