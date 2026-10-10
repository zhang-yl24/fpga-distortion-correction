`timescale 1ns/1ps
// Probe only: releases RESETB after a >=1ms low pulse, waits >20ms, then
// reads 0x300A/0x300B at candidate OV5640 address 0x3C. No init table writes.
// Reset is also open drain, relying on the sensor's documented pull-up.
module camera_id_probe #(parameter RESET_CYCLES=270000, parameter WAIT_CYCLES=1350000)(
    input clk, input rst_n, inout cam_rst_n, inout cam_scl, inout cam_sda,
    output reg [15:0] sensor_id, output reg [7:0] errors,
    output reg complete, output match_5640
);
    reg [31:0] count;
    reg [2:0] state;
    reg trigger;
    reg reset_low=1'b1;
    wire busy, done;
    wire [3:0] error;
    wire [7:0] data;
    assign cam_rst_n = reset_low ? 1'b0:1'bz;
    assign match_5640 = complete && errors==0 && sensor_id==16'h5640;
    reg16_i2c i2c(.clk(clk),.rst_n(rst_n),.start(trigger),.read(1'b1),
        .device(7'h3c),.address(state<3 ? 16'h300a:16'h300b),.write_data(8'h00),
        .busy(busy),.done(done),.error(error),.read_data(data),.scl(cam_scl),.sda(cam_sda));
    always @(posedge clk) begin
        if(!rst_n) begin reset_low<=1;state<=0; count<=0; trigger<=0; sensor_id<=0; errors<=0; complete<=0; end
        else begin
            trigger<=0;
            case(state)
                0: if(count==RESET_CYCLES-1) begin reset_low<=0;count<=0; state<=1; end
                    else begin reset_low<=1;count<=count+1;end
                1: if(count==WAIT_CYCLES-1) begin count<=0; state<=2; trigger<=1; end else count<=count+1;
                2: if(done) begin sensor_id[15:8]<=data; errors[7:4]<=error; state<=3; end
                3: begin trigger<=1; state<=4; end
                4: if(done) begin sensor_id[7:0]<=data; errors[3:0]<=error; complete<=1; state<=5; end
                5: if(count==27000000-1) begin count<=0; complete<=0; state<=1; end else count<=count+1;
                default: begin reset_low<=1;state<=0;count<=0;end
            endcase
        end
    end
endmodule
