`timescale 1ns/1ps
module tb_ov5640_pad_sweep;
    reg clk=0; always #5 clk=~clk;
    reg rst_n=0;
    tri1 cam_rst_n,cam_scl,cam_sda;
    reg slave_low=0;
    assign cam_sda=slave_low ? 1'b0:1'bz;
    wire [15:0] sensor_id,failed_address; wire ready,failed;
    wire [7:0] error_code; wire [8:0] commands_written;
    wire [8:0] verified_write_noacks;
    wire [7:0] observed_value,expected_value;
    wire [3:0] trial;wire [15:0] pad_mask;
    ov5640_pad_sweep #(.GAP_CYCLES(10),.HOLD_CYCLES(1000),.WATCHDOG_CYCLES(200000),.RESET_CYCLES(8),.WAIT_CYCLES(12),.MS_CYCLES(2),
        .I2C_QUARTER_CYCLES(2),.I2C_TIMEOUT_CYCLES(4000)) dut(.*);
    reg [7:0] registers[0:65535];
    integer writes=0; reg corrupt=0, bad_pad=0;
    task automatic get_start;
        begin do @(negedge cam_sda); while(cam_scl!==1); end
    endtask
    task automatic get_byte(output reg [7:0] value,input bit ack);
        begin
            value=0;
            repeat(8) begin @(posedge cam_scl); value={value[6:0],cam_sda}; end
            @(negedge cam_scl); slave_low=ack;
            @(posedge cam_scl); @(negedge cam_scl); slave_low=0;
        end
    endtask
    task automatic expect_byte(input [7:0] expected,input bit ack);
        reg [7:0] value;
        begin get_byte(value,ack); if(value!==expected) $fatal(1,"SCCB byte %h vs %h",value,expected); end
    endtask
    task automatic reply(input [7:0] value);
        begin
            for(integer i=7;i>=0;i=i-1) begin
                slave_low=!value[i]; @(posedge cam_scl); @(negedge cam_scl);
            end
            slave_low=0; @(posedge cam_scl);
            if(cam_sda!==1) $fatal(1,"Read must end with NACK");
            @(negedge cam_scl);
        end
    endtask
    task automatic register_read(input [15:0] address,input [7:0] value);
        begin
            get_start(); expect_byte(8'h78,1); expect_byte(address[15:8],1); expect_byte(address[7:0],1);
            get_start(); expect_byte(8'h79,1); reply(value);
        end
    endtask
    task automatic register_write(input bit acknowledge);
        reg [7:0] hi,lo,value;
        begin
            get_start(); expect_byte(8'h78,1); get_byte(hi,1);get_byte(lo,1);get_byte(value,acknowledge);
            if(acknowledge) begin
                registers[{hi,lo}]=value;writes=writes+1;
                if(dut.camera.checkable_write({hi,lo})) register_read({hi,lo},bad_pad && {hi,lo}==16'h3018 ? 8'h00:value);
            end
        end
    endtask
    task automatic reset_camera;
        begin
            @(negedge clk);rst_n=0;slave_low=0;repeat(5) @(negedge clk);rst_n=1;
        end
    endtask

    task automatic configure_trial;
        begin
            register_read(16'h300a,8'h56);register_read(16'h300b,8'h40);
            repeat(263) register_write(1);
            register_read(16'h3808,registers[16'h3808]);register_read(16'h3809,registers[16'h3809]);
            register_read(16'h380a,registers[16'h380a]);register_read(16'h380b,registers[16'h380b]);
            register_read(16'h4300,registers[16'h4300]);register_read(16'h501f,registers[16'h501f]);
            register_read(16'h4740,registers[16'h4740]);
            register_write(1);
            register_read(16'h3808,registers[16'h3808]);register_read(16'h3809,registers[16'h3809]);
            register_read(16'h380a,registers[16'h380a]);register_read(16'h380b,registers[16'h380b]);
            register_read(16'h4300,registers[16'h4300]);register_read(16'h501f,registers[16'h501f]);
            register_read(16'h4740,registers[16'h4740]);
        end
    endtask
    reg [15:0] expected_masks[0:13];
    initial begin
        expected_masks[0]=16'h0000;expected_masks[1]=16'h1000;expected_masks[2]=16'h2000;
        expected_masks[3]=16'h4000;expected_masks[4]=16'h7000;expected_masks[5]=16'h7100;
        expected_masks[6]=16'h7200;expected_masks[7]=16'h7400;expected_masks[8]=16'h7800;
        expected_masks[9]=16'h7010;expected_masks[10]=16'h7020;expected_masks[11]=16'h7040;
        expected_masks[12]=16'h7080;expected_masks[13]=16'h7ff0;
        #100;reset_camera();
        for(integer n=0;n<14;n=n+1) begin
            configure_trial();wait(ready);#1;
            if(failed || commands_written!==264 || sensor_id!==16'h5640 || trial!==n ||
                registers[16'h3017]!==expected_masks[n][15:8] || registers[16'h3018]!==expected_masks[n][7:0])
                $fatal(1,"Trial %0d mask/reset/readback incorrect",n);
            @(negedge cam_rst_n);
        end
        wait(trial==0);#1;
        if(ready || failed) $fatal(1,"Prior trial status not cleared after wrap");
        // No slave response: bounded NACK failure then next independent trial.
        wait(failed);if(error_code!==8'h11) $fatal(1,"Expected ID address NACK");
        @(negedge cam_rst_n);wait(trial==1);#1;
        if(ready || failed) $fatal(1,"Failure not cleared at next reset");
        $display("PASS pad_sweep all 14 masks on real I2C RTL, reset per trial, failure progression and wrap");$finish;
    end
    initial begin #60000000;$fatal(1,"Sweep timeout");end
endmodule
