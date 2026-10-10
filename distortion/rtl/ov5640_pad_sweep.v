`timescale 1ns/1ps
// Independent, bounded trials: reset/re-identify the physical sensor each time.
// The pair is 3017:3018. Never enable FREX, D1/D0 or GPIO outputs.
module ov5640_pad_sweep #(
    parameter GAP_CYCLES=270000, HOLD_CYCLES=135000000,
    WATCHDOG_CYCLES=54000000,
    RESET_CYCLES=270000, WAIT_CYCLES=1350000, MS_CYCLES=27000,
    I2C_QUARTER_CYCLES=68, I2C_TIMEOUT_CYCLES=1350000
)(input clk,rst_n, inout cam_rst_n,cam_scl,cam_sda,
    output [15:0] sensor_id, output ready,failed,
    output [7:0] error_code, output [15:0] failed_address,
    output [8:0] commands_written,verified_write_noacks,
    output [7:0] observed_value,expected_value,
    output reg [3:0] trial, output [15:0] pad_mask);
    reg [1:0] state;
    reg [31:0] count;
    reg init_reset_n=0;
    reg watchdog_failed;
    wire init_failed;
    function [15:0] mask;
        input [3:0] n;
        begin case(n)
            0:mask=16'h0000; // All pads off
            1:mask=16'h1000; // PCLK only
            2:mask=16'h2000; // HREF only
            3:mask=16'h4000; // VSYNC only
            4:mask=16'h7000; // All sync/clock, data off
            5:mask=16'h7100; // Sensor D6 (module D4)
            6:mask=16'h7200; // Sensor D7 (module D5)
            7:mask=16'h7400; // Sensor D8 (module D6)
            8:mask=16'h7800; // Sensor D9 (module D7)
            9:mask=16'h7010; // Sensor D2 (module D0)
            10:mask=16'h7020;// Sensor D3 (module D1)
            11:mask=16'h7040;// Sensor D4 (module D2)
            12:mask=16'h7080;// Sensor D5 (module D3)
            default:mask=16'h7ff0;
        endcase end
    endfunction
    assign pad_mask=mask(trial);
    assign failed=init_failed || watchdog_failed;
    always @(posedge clk) begin
        if(!rst_n) begin
            state<=0;count<=0;trial<=0;init_reset_n<=0;watchdog_failed<=0;
        end else case(state)
            0:if(count==GAP_CYCLES-1) begin count<=0;init_reset_n<=1;state<=1;end
                else count<=count+1;
            1:if(ready || init_failed || count==WATCHDOG_CYCLES-1) begin
                    watchdog_failed<=!(ready || init_failed);count<=0;state<=2;
                end else count<=count+1;
            2:if(count==HOLD_CYCLES-1) begin
                    init_reset_n<=0;count<=0;watchdog_failed<=0;
                    trial<=trial==13 ? 0:trial+1'b1;state<=0;
                end else count<=count+1;
            default:begin state<=0;count<=0;init_reset_n<=0;end
        endcase
    end
    ov5640_init #(.DYNAMIC_PAD_MASK(1),.RESET_CYCLES(RESET_CYCLES),
        .WAIT_CYCLES(WAIT_CYCLES),.MS_CYCLES(MS_CYCLES),
        .I2C_QUARTER_CYCLES(I2C_QUARTER_CYCLES),.I2C_TIMEOUT_CYCLES(I2C_TIMEOUT_CYCLES))
        camera(.clk(clk),.rst_n(rst_n && init_reset_n),.trial_pad_mask(pad_mask),
        .cam_rst_n(cam_rst_n),.cam_scl(cam_scl),.cam_sda(cam_sda),
        .sensor_id(sensor_id),.ready(ready),.failed(init_failed),.error_code(error_code),
        .failed_address(failed_address),.commands_written(commands_written),
        .verified_write_noacks(verified_write_noacks),.observed_value(observed_value),
        .expected_value(expected_value));
endmodule
