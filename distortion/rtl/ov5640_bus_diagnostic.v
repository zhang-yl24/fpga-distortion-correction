`timescale 1ns/1ps
// Repeating isolated-register experiment; deliberately bypasses the init table.
// W is the test index, N selects STOP reads (1) vs repeated START (0).
module ov5640_bus_diagnostic #(
    parameter RESET_CYCLES=270000, WAIT_CYCLES=1350000,
    HOLD_CYCLES=54000000, QUARTER_CYCLES=68
)(input clk, rst_n, inout cam_rst_n,cam_scl,cam_sda,
    output reg [15:0] sensor_id,
    output ready, failed, output reg [7:0] error_code,
    output reg [15:0] failed_address,
    output reg [8:0] commands_written, verified_write_noacks,
    output reg [7:0] observed_value, expected_value);
    reg [2:0] state;
    reg [31:0] count;
    reg reset_low=1;
    reg [3:0] step;
    reg trigger, rd, stop_mode;
    reg [15:0] addr;
    reg [7:0] data;
    wire [1:0] done; wire [3:0] err0,err1;
    wire [7:0] val0,val1;
    assign cam_rst_n=reset_low ? 1'b0:1'bz;
    assign ready=state==4;
    assign failed=0;
    reg16_i2c #(.QUARTER_CYCLES(QUARTER_CYCLES)) repeated_bus(
        .clk(clk),.rst_n(rst_n),.start(trigger && !stop_mode),.read(rd),
        .device(7'h3c),.address(addr),.write_data(data),.done(done[0]),
        .error(err0),.read_data(val0),.scl(cam_scl),.sda(cam_sda));
    reg16_i2c #(.QUARTER_CYCLES(QUARTER_CYCLES),.READ_WITH_STOP(1)) stop_bus(
        .clk(clk),.rst_n(rst_n),.start(trigger && stop_mode),.read(rd),
        .device(7'h3c),.address(addr),.write_data(data),.done(done[1]),
        .error(err1),.read_data(val1),.scl(cam_scl),.sda(cam_sda));
    // bits: stop-mode, read, address, value. Read expected values are labels,
    // not pass criteria; initial defaults depend on the sensor's current state.
    function [25:0] operation;
        input [3:0] i;
        begin case(i)
            0:operation={1'b0,1'b1,16'h300a,8'h56};
            1:operation={1'b1,1'b1,16'h300b,8'h40};
            2:operation={1'b0,1'b1,16'h4740,8'h20};
            3:operation={1'b0,1'b0,16'h4740,8'h23};
            4:operation={1'b0,1'b1,16'h4740,8'h23};
            5:operation={1'b1,1'b1,16'h4740,8'h23};
            6:operation={1'b1,1'b0,16'h4740,8'h20};
            7:operation={1'b1,1'b1,16'h4740,8'h20};
            8:operation={1'b0,1'b1,16'h4740,8'h20};
            9:operation={1'b1,1'b0,16'h3808,8'h02};
            10:operation={1'b1,1'b1,16'h3808,8'h02};
            11:operation={1'b0,1'b1,16'h3808,8'h02};
            12:operation={1'b1,1'b1,16'h3008,8'h02};
            13:operation={1'b1,1'b1,16'h3103,8'h11};
            default:operation=0;
        endcase end
    endfunction
    wire [25:0] op=operation(step);
    always @(posedge clk) begin
        if(!rst_n) begin
            state<=0;count<=0;reset_low<=1;step<=0;trigger<=0;rd<=1;stop_mode<=0;
            addr<=0;data<=0;sensor_id<=0;error_code<=0;failed_address<=0;
            commands_written<=0;verified_write_noacks<=0;observed_value<=0;expected_value<=0;
        end else begin
            trigger<=0;
            case(state)
                0: if(count==RESET_CYCLES-1) begin reset_low<=0;count<=0;state<=1;end else count<=count+1;
                1: if(count==WAIT_CYCLES-1) begin count<=0;state<=2;end else count<=count+1;
                2: begin stop_mode<=op[25];rd<=op[24];addr<=op[23:8];data<=op[7:0];trigger<=1;state<=3;end
                3: if(stop_mode ? done[1]:done[0]) begin
                    observed_value<=stop_mode ? val1:val0;expected_value<=data;
                    error_code<={3'b0,rd,stop_mode ? err1:err0};failed_address<=addr;
                    commands_written<={5'b0,step};verified_write_noacks<={8'b0,stop_mode};
                    if(step==0) sensor_id[15:8]<=val0;
                    if(step==1) sensor_id[7:0]<=val1;
                    count<=0;state<=4;
                end
                4: if(count==HOLD_CYCLES-1) begin
                    count<=0;step<=step==13 ? 0:step+1;state<=2;
                end else count<=count+1;
                default: state<=0;
            endcase
        end
    end
endmodule
