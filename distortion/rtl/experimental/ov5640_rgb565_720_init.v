`timescale 1ns/1ps
// Independent conditional84/4 RGB565720 register sequencer.
// configured means critical register readback only, NEVER raw/mode admission.
// A separate measured PCLK/activity/line/frame-freshness gate is still required.
module ov5640_rgb565_720_init #(
    parameter RESET_CYCLES=270000,WAIT_CYCLES=1350000,MS_CYCLES=27000,
    I2C_QUARTER_CYCLES=68,I2C_TIMEOUT_CYCLES=1350000
)(input clk,rst_n,inout cam_rst_n,cam_scl,cam_sda,
    output reg [15:0] sensor_id,output reg configured,failed,
    output reg [7:0] error_code,output reg [15:0] failed_address,
    output reg [7:0] observed_value,expected_value,output reg observed_valid,
    output reg [3:0] last_bus_error,
    output reg [9:0] action_index,failed_action,writes_completed,verified_write_noacks,
    output reg final_wake_verified);
    `include "D:/English/FPGA/distortion/board/ov5640_rgb565_720_commands.vh"
    localparam RESET=0,WAIT=1,ID_H=2,ID_H_WAIT=3,ID_L=4,ID_L_WAIT=5,CHECK_ID=6,
        EXECUTE=7,PRE_WAIT=8,WRITE_START=9,WRITE_WAIT=10,READBACK_START=11,
        READBACK_WAIT=12,CHECK_WAIT=13,DELAY=14,FINISHED=15,FAULT=16;
    reg [4:0] state;
    reg reset_low=1,trigger,read_mode,pending_noack;
    reg [31:0] counter,delay_cycles;
    reg [15:0] address;reg [7:0] write_data;
    wire busy,done;wire [3:0] bus_error;wire [7:0] read_data;
    wire [47:0] command=mode_action(action_index);
    wire [3:0] action_op=command[47:44];
    wire [15:0] action_address=command[43:28];
    wire [7:0] action_mask=command[27:20],action_value=command[19:12];
    assign cam_rst_n=reset_low ? 1'b0:1'bz;
    reg16_i2c #(.QUARTER_CYCLES(I2C_QUARTER_CYCLES),.TIMEOUT_CYCLES(I2C_TIMEOUT_CYCLES)) bus(
        .clk(clk),.rst_n(rst_n),.start(trigger),.read(read_mode),.device(7'h3c),.address(address),.write_data(write_data),
        .busy(busy),.done(done),.error(bus_error),.read_data(read_data),.scl(cam_scl),.sda(cam_sda));
    task fail;
        input [7:0] code;
        begin failed<=1;configured<=0;error_code<=code;failed_address<=address;
            failed_action<=action_index;state<=FAULT;end
    endtask
    task advance;
        begin
            if(action_index==MODE_ACTIONS-1)state<=FINISHED;
            else begin action_index<=action_index+1'b1;state<=EXECUTE;end
        end
    endtask
    task delay_or_advance;
        begin
            if(command[11:0]!=0)begin delay_cycles<=command[11:0]*MS_CYCLES;counter<=0;state<=DELAY;end
            else advance();
        end
    endtask
    always @(posedge clk)begin
        if(!rst_n)begin
            state<=RESET;reset_low<=1;trigger<=0;read_mode<=1;pending_noack<=0;
            counter<=0;delay_cycles<=0;address<=0;write_data<=0;sensor_id<=0;
            configured<=0;failed<=0;error_code<=0;failed_address<=0;observed_value<=0;expected_value<=0;
            observed_valid<=0;last_bus_error<=0;action_index<=0;failed_action<=0;
            writes_completed<=0;verified_write_noacks<=0;final_wake_verified<=0;
        end else begin
            trigger<=0;
            if(done)begin last_bus_error<=bus_error;observed_value<=read_data;observed_valid<=read_mode && bus_error==0;end
            case(state)
                RESET:if(counter==RESET_CYCLES-1)begin reset_low<=0;counter<=0;state<=WAIT;end else counter<=counter+1'b1;
                WAIT:if(counter==WAIT_CYCLES-1)begin counter<=0;state<=ID_H;end else counter<=counter+1'b1;
                ID_H:begin address<=16'h300a;read_mode<=1;trigger<=1;state<=ID_H_WAIT;end
                ID_H_WAIT:if(done)begin if(bus_error!=0)fail({4'h1,bus_error});else begin sensor_id[15:8]<=read_data;state<=ID_L;end end
                ID_L:begin address<=16'h300b;trigger<=1;state<=ID_L_WAIT;end
                ID_L_WAIT:if(done)begin if(bus_error!=0)fail({4'h1,bus_error});else begin sensor_id[7:0]<=read_data;state<=CHECK_ID;end end
                CHECK_ID:if(sensor_id!=16'h5640)fail(8'h20);else state<=EXECUTE;
                EXECUTE:begin
                    address<=action_address;expected_value<=action_value;pending_noack<=0;
                    if(action_op==2)begin read_mode<=1;trigger<=1;state<=PRE_WAIT;end
                    else if(action_op==3)begin read_mode<=1;trigger<=1;state<=CHECK_WAIT;end
                    else if(action_op==1 || action_op==5)begin write_data<=action_value;state<=WRITE_START;end
                    else fail(8'hf0);
                end
                PRE_WAIT:if(done)begin
                    if(bus_error!=0)fail({4'h2,bus_error});
                    else begin write_data<=(read_data & ~action_mask)|action_value;state<=WRITE_START;end
                end
                WRITE_START:begin read_mode<=0;trigger<=1;state<=WRITE_WAIT;end
                WRITE_WAIT:if(done)begin
                    if(bus_error==4 && action_op!=5)begin pending_noack<=1;state<=READBACK_START;end
                    else if(bus_error!=0)fail({4'h3,bus_error});
                    else if(action_mask!=0)state<=READBACK_START;
                    else begin writes_completed<=writes_completed+1'b1;delay_or_advance();end
                end
                READBACK_START:begin read_mode<=1;trigger<=1;state<=READBACK_WAIT;end
                READBACK_WAIT:if(done)begin
                    expected_value<=write_data;
                    if(bus_error!=0)fail({4'h6,bus_error});
                    // Full-byte equality is mandatory even for a masked RMW.
                    // A masked match never excuses an unverified final-data high.
                    else if(read_data!=write_data)fail(8'h70);
                    else begin
                        writes_completed<=writes_completed+1'b1;
                        if(pending_noack)verified_write_noacks<=verified_write_noacks+1'b1;
                        if(action_index==MODE_WAKE)final_wake_verified<=1;
                        delay_or_advance();
                    end
                end
                CHECK_WAIT:if(done)begin
                    if(bus_error!=0)fail({4'h4,bus_error});
                    else if((read_data & action_mask)!=(action_value & action_mask))fail(8'h50);
                    else delay_or_advance();
                end
                DELAY:if(counter>=delay_cycles)advance();else counter<=counter+1'b1;
                FINISHED:configured<=1;
                FAULT:begin failed<=1;configured<=0;end
                default:fail(8'hff);
            endcase
        end
    end
endmodule
