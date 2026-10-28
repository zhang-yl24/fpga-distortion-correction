`timescale 1ns/1ps
module tb_guarded_temperature_cdc;
    reg source_clk=0,core_clk=0,source_running=1,arst_n=0;
    always #18 if(source_running)source_clk=~source_clk;
    always #4 core_clk=~core_clk;
    reg sample_valid=0,failed=0,over_temp=0;reg [7:0] fault=0;
    reg [4:0] alarm=0;reg [15:0] raw_word=16'h9d60;reg [11:0] code12=2518;
    reg [31:0] sample_age=3,samples=2,conversions=100;reg [95:0] source_extra=2;
    wire healthy,snapshot_valid,snapshot_event,held_valid,held_failed,held_over_temp;
    wire [31:0] snapshot_age,held_age,held_samples,held_conversions;
    wire [15:0] held_raw;wire [11:0] held_code;wire [7:0] held_fault;wire [4:0] held_alarm;
    wire [95:0] held_extra;
    guarded_temperature_cdc #(.SNAPSHOT_CYCLES(8),.CORE_MAX_AGE(80),.SOURCE_MAX_AGE(1000)) dut(.*);
    task wait_healthy;
        input expected;integer limit;
        begin limit=0;while(healthy!==expected && limit<250)begin @(negedge core_clk);limit=limit+1;end
            if(healthy!==expected)$fatal(1,"Temperature healthy timeout wanted %d age %d",expected,snapshot_age);
        end
    endtask
    always @(negedge core_clk)if(snapshot_event)begin
        if(held_raw!={held_code,4'b0} || held_extra[31:0]!=held_samples)
            $fatal(1,"Temperature held-bus snapshot tore");
    end
    integer i;
    initial begin
        repeat(5)@(negedge core_clk);arst_n=1;
        repeat(150)@(negedge core_clk);if(healthy)$fatal(1,"Boot accepted invalid ADC");
        sample_valid=1;wait_healthy(1);
        for(i=0;i<15;i=i+1)begin
            @(negedge source_clk);samples=samples+1;source_extra=samples;conversions=conversions+7;
            code12=2518+i%2;raw_word={code12,4'b0};
        end
        over_temp=1;wait_healthy(0);over_temp=0;wait_healthy(1);
        failed=1;fault=8'h72;wait_healthy(0);
        repeat(150)@(negedge core_clk);
        if(!held_failed || held_fault!=8'h72)$fatal(1,"ADC failure is not observable");
        failed=0;fault=0;wait_healthy(1);
        alarm=1;wait_healthy(0);alarm=0;wait_healthy(1);
        sample_age=1000;wait_healthy(0);sample_age=3;wait_healthy(1);
        code12=1912;raw_word={code12,4'b0};wait_healthy(0);
        code12=1913;raw_word={code12,4'b0};wait_healthy(1);
        code12=2733;raw_word={code12,4'b0};wait_healthy(0);
        code12=2732;raw_word={code12,4'b0};wait_healthy(1);
        // Halt source oscillator while its last registered healthy bit is 1.
        @(negedge source_clk);source_running=0;repeat(120)@(negedge core_clk);
        if(healthy || snapshot_age<80)$fatal(1,"Core watchdog did not independently expire");
        source_running=1;wait_healthy(1);
        arst_n=0;#1;if(healthy || snapshot_valid)$fatal(1,"Async reset not fail closed");
        repeat(7)@(negedge core_clk);sample_valid=0;arst_n=1;
        repeat(150)@(negedge core_clk);
        if(healthy || held_valid)$fatal(1,"Stale pre-reset ADC snapshot accepted");
        $display("PASS guarded temperature CDC: atomic held bus, invalid/failure/age/range/alarm gating, source clock halt watchdog, shared reset fail closed.");$finish;
    end
    initial begin #100000;$fatal(1,"Temperature CDC regression timeout");end
endmodule
