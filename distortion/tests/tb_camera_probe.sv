`timescale 1ns/1ps
module tb_camera_probe;
    reg clk=0; always #5 clk=~clk;
    reg rst_n=0;
    tri1 cam_rst_n,cam_scl,cam_sda;
    reg slave_low=0;
    assign cam_sda=slave_low ? 1'b0:1'bz;
    wire [15:0] sensor_id; wire [7:0] errors;
    wire complete,match_5640;
    camera_id_probe #(.RESET_CYCLES(8),.WAIT_CYCLES(12)) dut(.*);
    task automatic get_start;
        begin do @(negedge cam_sda); while(cam_scl!==1); end
    endtask
    task automatic get_byte(input [7:0] expected,input bit ack);
        reg [7:0] value;
        begin
            value=0;
            repeat(8) begin @(posedge cam_scl); value={value[6:0],cam_sda}; end
            if(value!==expected) $fatal(1,"Wrong probe byte %h vs %h",value,expected);
            @(negedge cam_scl); slave_low=ack;
            @(posedge cam_scl); @(negedge cam_scl); slave_low=0;
        end
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
    task automatic register_read(input [7:0] low_address,input [7:0] value);
        begin
            get_start(); get_byte(8'h78,1); get_byte(8'h30,1); get_byte(low_address,1);
            get_start(); get_byte(8'h79,1); reply(value);
        end
    endtask
    initial begin
        #100; @(negedge clk); rst_n=1;
        register_read(8'h0a,8'h56); register_read(8'h0b,8'h40);
        @(posedge complete); #1;
        if(sensor_id!==16'h5640 || errors!==0 || !match_5640) $fatal(1,"Probe did not identify sensor");
        @(negedge clk); rst_n=0; repeat(5) @(negedge clk); rst_n=1;
        get_start(); get_byte(8'h78,0);
        register_read(8'h0b,8'h40);
        @(posedge complete); #1;
        if(errors!==8'h10 || match_5640) $fatal(1,"Failed ID read incorrectly accepted");
        $display("PASS camera_probe ID 5640 and NACK rejection; correct 300A/300B order"); $finish;
    end
    initial begin #2000000; $fatal(1,"Probe timeout"); end
endmodule
