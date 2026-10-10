`timescale 1ns/1ps
module tb_adc_temperature_reader;
    reg clk=0;always #18.5 clk=~clk;
    reg rst_n=0,adc_done=0,adc_drdy=0;reg [15:0] adc_do=0;
    wire den,secen,dwe;wire [7:0] daddr;wire [15:0] di;
    wire sample_valid,sample_pulse,failed;wire [7:0] fault;
    wire [15:0] raw_word;wire [11:0] code12;wire [31:0] sample_age,conversions,samples;
    adc_temperature_reader #(.STARTUP_CYCLES(16),.PERIOD_CYCLES(40),.TIMEOUT_CYCLES(30),.STALE_CYCLES(100)) dut(.*);
    integer ticks=0,den_cycles=0,delay=0,received=0;reg stop_done=0,drop_response=0,zero_response=0,hold_response=0;
    reg active=0;reg [11:0] current_code=12'h98d;
    always @(negedge clk) begin
        ticks=ticks+1;
        adc_done=rst_n && !stop_done && ticks%8==0;
    end
    always @(posedge clk) begin
        if(!rst_n) begin adc_drdy<=0;active<=0;delay<=0;den_cycles<=0;end
        else begin
            if(den) den_cycles<=den_cycles+1;else den_cycles<=0;
            if(secen && !active && !adc_drdy) begin
                if(den_cycles<2 || !den || dwe || daddr!=8'h40 || conversions<3) $fatal(1,"Bad ADC transaction setup or first conversions not discarded");
                active<=1;delay<=6;
            end
            if(active && !adc_drdy && !drop_response) begin
                if(delay>0) delay<=delay-1;
                else begin adc_do<=zero_response ? 16'h000f:{current_code,4'hf};adc_drdy<=1;end
            end
            if(!secen && adc_drdy && !hold_response) begin adc_drdy<=0;active<=0;current_code<=current_code+1'b1;end
            if(sample_pulse) begin
                if(!sample_valid || code12!==raw_word[15:4] || raw_word[3:0]!=15 || code12==0) $fatal(1,"Bad fresh ADC sample or wrong 12-bit extraction");
                received<=received+1;
            end
        end
    end
    task reset;
        begin @(negedge clk);rst_n=0;repeat(8) @(negedge clk);rst_n=1;end
    endtask
    initial begin
        reset;wait(received>=3);stop_done=1;wait(!den && !secen);wait(!sample_valid);
        if(failed || samples<3) $fatal(1,"Stale sample handling failed");
        stop_done=0;drop_response=1;reset;wait(failed);
        if(fault!=1 || sample_valid || den || secen) $fatal(1,"Missing DRDY timeout not quarantined");
        drop_response=0;zero_response=1;reset;wait(failed);
        if(fault!=4 || sample_valid) $fatal(1,"Uninitialized zero conversion treated as temperature");
        zero_response=0;hold_response=1;reset;wait(failed);
        if(fault!=2 || sample_valid) $fatal(1,"Stuck DRDY not rejected");
        hold_response=0;reset;wait(sample_valid);
        $display("PASS ADC readback adapter: bias settle, first-two-conversion discard, DEN setup, 0x40 read, high12 extraction, fresh/stale validity, missing/stuck DRDY, zero-word rejection and reset recovery. Analog behavior not simulated.");$finish;
    end
    initial begin #1000000;$fatal(1,"ADC adapter timeout");end
endmodule
