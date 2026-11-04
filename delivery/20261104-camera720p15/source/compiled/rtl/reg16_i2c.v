`timescale 1ns/1ps
// Single register transaction, 7-bit device address, 16-bit register, 8-bit data.
// Both wires are open drain. Checks ACKs, supports clock stretching, times out.
// MS7210 uses little-endian register addresses; OV5640 uses big-endian.
module reg16_i2c #(
    parameter QUARTER_CYCLES = 68,
    parameter TIMEOUT_CYCLES = 1350000,
    parameter ADDR_LSB_FIRST = 0,
    // SCCB hosts commonly terminate the register-address phase with STOP.
    parameter READ_WITH_STOP = 0
)(
    input clk, input rst_n, input start, input read,
    input [6:0] device, input [15:0] address, input [7:0] write_data,
    output reg busy, output reg done, output reg [3:0] error,
    output reg [7:0] read_data, inout scl, inout sda
);
    localparam IDLE=0, START0=1, START1=2, TX0=3, TX1=4, TX2=5, TX3=6,
        ACK0=7, ACK1=8, ACK2=9, ACK3=10, RE0=11, RE1=12, RE2=13,
        RX0=14, RX1=15, RX2=16, RX3=17, NACK0=18, NACK1=19,
        NACK2=20, NACK3=21, STOP0=22, STOP1=23, STOP2=24, BUS_FREE=25;
    reg [4:0] state;
    reg scl_low, sda_low;
    assign scl = scl_low ? 1'b0 : 1'bz;
    assign sda = sda_low ? 1'b0 : 1'bz;
    (* async_reg = "true" *) reg scl_meta, scl_sampled, sda_meta, sda_sampled;
    always @(posedge clk) begin
        scl_meta <= scl; scl_sampled <= scl_meta;
        sda_meta <= sda; sda_sampled <= sda_meta;
    end
    reg [31:0] divider, watchdog;
    reg [6:0] dev;
    reg [15:0] addr;
    reg [7:0] data, tx;
    reg rd, nack, pending_read;
    reg [2:0] bit_index, byte_index;
    // Freeze each released-high phase until the slave releases SCL.
    wire stretch = !scl_low && !scl_sampled;
    always @(posedge clk) begin
        if (!rst_n) begin
            state<=IDLE; busy<=0; done<=0; error<=0; read_data<=0;
            scl_low<=0; sda_low<=0; divider<=0; watchdog<=0;
            dev<=0; addr<=0; data<=0; tx<=0; rd<=0; nack<=0; pending_read<=0;
            bit_index<=7; byte_index<=0;
        end else begin
            done <= 0;
            if (state==IDLE) begin
                divider<=0; watchdog<=0; scl_low<=0; sda_low<=0;
                if(start) begin
                    busy<=1; error<=0; read_data<=0;
                    dev<=device; addr<=address; data<=write_data; rd<=read;
                    tx<={device,1'b0}; bit_index<=7; byte_index<=0; pending_read<=0;
                    state<=START0;
                end
            end else if(watchdog>=TIMEOUT_CYCLES-1) begin
                // Bus held low: release outputs, report failure, never hang.
                scl_low<=0; sda_low<=0; busy<=0; done<=1; error<=4'hf;
                state<=IDLE;
            end else begin
                watchdog<=watchdog+1;
                if(stretch || (state==START0 && !sda_sampled)) divider<=0;
                else if(divider==QUARTER_CYCLES-1) begin
                    divider<=0;
                    case(state)
                        START0: begin sda_low<=1; state<=START1; end
                        START1: begin scl_low<=1; state<=TX0; end
                        TX0: begin sda_low<=!tx[bit_index]; state<=TX1; end
                        TX1: begin scl_low<=0; state<=TX2; end
                        TX2: state<=TX3;
                        TX3: begin
                            scl_low<=1;
                            if(bit_index==0) state<=ACK0;
                            else begin bit_index<=bit_index-1; state<=TX0; end
                        end
                        ACK0: begin sda_low<=0; state<=ACK1; end
                        ACK1: begin scl_low<=0; state<=ACK2; end
                        ACK2: begin nack<=sda_sampled; state<=ACK3; end
                        ACK3: begin
                            scl_low<=1; bit_index<=7;
                            if(nack) begin error<={1'b0,byte_index}+1'b1; state<=STOP0; end
                            else case(byte_index)
                                0: begin tx<=ADDR_LSB_FIRST ? addr[7:0]:addr[15:8]; byte_index<=1; state<=TX0; end
                                1: begin tx<=ADDR_LSB_FIRST ? addr[15:8]:addr[7:0]; byte_index<=2; state<=TX0; end
                                2: begin
                                    byte_index<=3;
                                    if(rd) begin
                                        tx<={dev,1'b1};
                                        if(READ_WITH_STOP) begin pending_read<=1; state<=STOP0; end
                                        else state<=RE0;
                                    end
                                    else begin tx<=data; state<=TX0; end
                                end
                                3: state<=rd ? RX0:STOP0;
                                default: state<=STOP0;
                            endcase
                        end
                        RE0: begin sda_low<=0; state<=RE1; end
                        RE1: begin scl_low<=0; state<=RE2; end
                        RE2: begin sda_low<=1; state<=START1; end
                        RX0: begin sda_low<=0; state<=RX1; end
                        RX1: begin scl_low<=0; state<=RX2; end
                        RX2: begin read_data[bit_index]<=sda_sampled; state<=RX3; end
                        RX3: begin
                            scl_low<=1;
                            if(bit_index==0) state<=NACK0;
                            else begin bit_index<=bit_index-1; state<=RX0; end
                        end
                        NACK0: begin sda_low<=0; state<=NACK1; end
                        NACK1: begin scl_low<=0; state<=NACK2; end
                        NACK2: state<=NACK3;
                        NACK3: begin scl_low<=1; state<=STOP0; end
                        STOP0: begin sda_low<=1; state<=STOP1; end
                        STOP1: begin scl_low<=0; state<=STOP2; end
                        STOP2: begin
                            sda_low<=0;
                            if(pending_read) begin pending_read<=0; state<=BUS_FREE; end
                            else begin busy<=0; done<=1; state<=IDLE; end
                        end
                        BUS_FREE: state<=START0;
                        default: begin state<=IDLE; busy<=0; end
                    endcase
                end else divider<=divider+1;
            end
        end
    end
endmodule
