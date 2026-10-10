`timescale 1ns/1ps
// Board DVP setup: identify silicon before writing the reference settings.
// Halt on address NACK, unverified data NACK, timeout, wrong ID or readback mismatch.
module ov5640_init #(
    parameter RESET_CYCLES=270000, WAIT_CYCLES=1350000,
    MS_CYCLES=27000, I2C_QUARTER_CYCLES=68, I2C_TIMEOUT_CYCLES=1350000,
    CHECK_WRITES=1, DYNAMIC_PAD_MASK=0
)(input clk, input rst_n, inout cam_rst_n, cam_scl, cam_sda,
    input [15:0] trial_pad_mask,
    output reg [15:0] sensor_id, output reg ready, output reg failed,
    output reg [7:0] error_code, output reg [15:0] failed_address,
    output reg [8:0] commands_written, output reg [8:0] verified_write_noacks,
    output reg [7:0] observed_value, expected_value);
    `include "D:/English/FPGA/distortion/board/ov5640_commands.vh"
    localparam RESET=0, WAIT=1, ID_H_START=2, ID_H_WAIT=3,
        ID_L_START=4, ID_L_WAIT=5, CHECK_ID=6, WRITE_START=7,
        WRITE_WAIT=8, DELAY=9, VERIFY_START=10, VERIFY_WAIT=11,
        FINISHED=12, FAILED=13, WRITE_READBACK_START=14, WRITE_READBACK_WAIT=15;
    reg [3:0] state;
    reg [31:0] count, delay_cycles;
    reg [8:0] command_index;
    reg [2:0] verify_index;
    reg verify_retry, write_noack, preflight_done;
    reg reset_low=1'b1;
    reg trigger, read_mode;
    reg [15:0] address;
    reg [7:0] write_data;
    wire [31:0] command=camera_command(command_index);
    wire busy, done; wire [3:0] bus_error; wire [7:0] read_data;
    // The external asynchronous reset must not decode a multi-bit FSM state:
    // transitions (e.g. 7 -> 8) can glitch through zero after routing.
    assign cam_rst_n=reset_low ? 1'b0:1'bz;
    reg16_i2c #(.QUARTER_CYCLES(I2C_QUARTER_CYCLES),.TIMEOUT_CYCLES(I2C_TIMEOUT_CYCLES))
        bus(.clk(clk),.rst_n(rst_n),.start(trigger),.read(read_mode),.device(7'h3c),
        .address(address),.write_data(write_data),.busy(busy),.done(done),
        .error(bus_error),.read_data(read_data),.scl(cam_scl),.sda(cam_sda));
    function [23:0] verify_command;
        input [2:0] index;
        begin case(index)
            0:verify_command=24'h380802; 1:verify_command=24'h380980;
            2:verify_command=24'h380a01; 3:verify_command=24'h380be0;
            4:verify_command=24'h43006f; 5:verify_command=24'h501f01;
            6:verify_command=24'h474023;
            default:verify_command=0;
        endcase end
    endfunction
    wire [23:0] verify_word=verify_command(verify_index);
    // Exact readback is meaningful for these documented configuration controls.
    // Do not require equality for undocumented debug/ISP status registers:
    // e.g. 5198..519D are labelled Debug Mode in the OV5640 datasheet.
    function checkable_write;
        input [15:0] a;
        begin case(a)
            16'h3103,16'h3108,16'h3034,16'h3035,16'h3036,16'h3037,
            16'h3017,16'h3018,16'h300e,
            16'h3808,16'h3809,16'h380a,16'h380b,
            16'h4300,16'h501f,16'h4740:checkable_write=1;
            default:checkable_write=0;
        endcase end
    endfunction
    always @(posedge clk) begin
        if(!rst_n) begin
            state<=RESET;count<=0;delay_cycles<=0;command_index<=0;verify_index<=0;
            trigger<=0;read_mode<=1;address<=0;write_data<=0;sensor_id<=0;
            ready<=0;failed<=0;error_code<=0;failed_address<=0;commands_written<=0;verified_write_noacks<=0;
            observed_value<=0;expected_value<=0;verify_retry<=0;reset_low<=1;write_noack<=0;preflight_done<=0;
        end else begin
            trigger<=0;
            case(state)
                RESET: if(count==RESET_CYCLES-1) begin reset_low<=0;count<=0;state<=WAIT;end
                    else begin reset_low<=1;count<=count+1;end
                WAIT: if(count==WAIT_CYCLES-1) begin count<=0;state<=ID_H_START;end else count<=count+1;
                ID_H_START: begin address<=16'h300a;read_mode<=1;trigger<=1;state<=ID_H_WAIT;end
                ID_H_WAIT: if(done) begin
                    if(bus_error!=0) begin error_code<={4'h1,bus_error};failed_address<=address;state<=FAILED;end
                    else begin sensor_id[15:8]<=read_data;state<=ID_L_START;end
                end
                ID_L_START: begin address<=16'h300b;trigger<=1;state<=ID_L_WAIT;end
                ID_L_WAIT: if(done) begin
                    if(bus_error!=0) begin error_code<={4'h1,bus_error};failed_address<=address;state<=FAILED;end
                    else begin sensor_id[7:0]<=read_data;state<=CHECK_ID;end
                end
                CHECK_ID: if(sensor_id==16'h5640) state<=WRITE_START;
                    else begin error_code<=8'h20;state<=FAILED;end
                WRITE_START: begin
                    if(command_index==CAMERA_COMMANDS-1 && !preflight_done) begin
                        verify_index<=0;state<=VERIFY_START;
                    end else begin
                        address<=command[31:16];read_mode<=0;
                        if(DYNAMIC_PAD_MASK && command[31:16]==16'h3017)
                            write_data<=trial_pad_mask[15:8];
                        else if(DYNAMIC_PAD_MASK && command[31:16]==16'h3018)
                            write_data<=trial_pad_mask[7:0];
                        else write_data<=command[15:8];
                        trigger<=1;state<=WRITE_WAIT;
                    end
                end
                WRITE_WAIT: if(done) begin
                    // SCCB's final write bit is Don't-Care. A high bit is
                    // accepted ONLY if a subsequent read returns the exact value.
                    if(bus_error==4) begin write_noack<=1;state<=WRITE_READBACK_START;end
                    else if(bus_error!=0) begin error_code<={4'h3,bus_error};failed_address<=address;state<=FAILED;end
                    // 3008 software-reset self-clears; its mandated delay is
                    // applied before the next command rather than exact readback.
                    else if(CHECK_WRITES && checkable_write(address)) begin write_noack<=0;state<=WRITE_READBACK_START;end
                    else begin
                        commands_written<=commands_written+1;
                        delay_cycles<=command[7:0]*MS_CYCLES;count<=0;state<=DELAY;
                    end
                end
                WRITE_READBACK_START: begin read_mode<=1;trigger<=1;state<=WRITE_READBACK_WAIT;end
                WRITE_READBACK_WAIT: if(done) begin
                    observed_value<=read_data;expected_value<=write_data;
                    if(bus_error!=0) begin error_code<={4'h6,bus_error};failed_address<=address;state<=FAILED;end
                    else if(read_data!=write_data) begin error_code<=8'h70;failed_address<=address;state<=FAILED;end
                    else begin
                        if(write_noack) verified_write_noacks<=verified_write_noacks+1;
                        commands_written<=commands_written+1;
                        delay_cycles<=command[7:0]*MS_CYCLES;count<=0;state<=DELAY;
                    end
                end
                DELAY: if(count>=delay_cycles) begin
                    count<=0;
                    if(command_index==CAMERA_COMMANDS-1) begin verify_index<=0;state<=VERIFY_START;end
                    else begin command_index<=command_index+1;state<=WRITE_START;end
                end else count<=count+1;
                VERIFY_START: begin address<=verify_word[23:8];read_mode<=1;trigger<=1;state<=VERIFY_WAIT;end
                VERIFY_WAIT: if(done) begin
                    observed_value<=read_data;expected_value<=verify_word[7:0];
                    if(bus_error!=0) begin error_code<={4'h4,bus_error};failed_address<=address;state<=FAILED;end
                    else if(read_data!=verify_word[7:0]) begin
                        // One bounded post-start retry, without rewriting or
                        // suppressing a mismatch. Then require all reads again.
                        if(!preflight_done) begin error_code<=8'h51;failed_address<=address;state<=FAILED;end
                        else if(!verify_retry) begin verify_retry<=1;delay_cycles<=500*MS_CYCLES;count<=0;state<=DELAY;end
                        else begin error_code<=8'h50;failed_address<=address;state<=FAILED;end
                    end
                    else if(verify_index==6) begin
                        if(!preflight_done) begin preflight_done<=1;state<=WRITE_START;end
                        else state<=FINISHED;
                    end
                    else begin verify_index<=verify_index+1;state<=VERIFY_START;end
                end
                FINISHED: ready<=1;
                FAILED: begin ready<=0;failed<=1;end
                default: begin reset_low<=1;state<=RESET;count<=0;end
            endcase
        end
    end
endmodule
