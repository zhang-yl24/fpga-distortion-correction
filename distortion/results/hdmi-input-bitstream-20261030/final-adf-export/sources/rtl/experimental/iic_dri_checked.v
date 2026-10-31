`timescale 1ns/1ps
// Isolated MS72xx register driver. Does not replace the audited vendor driver.
// Request-side names/widths match iic_dri; scl_in and sticky fault outputs are
// added. ONLY one data byte and a two-byte, low-byte-first register are supported.
// scl=1 means RELEASE: the wrapper MUST drive its physical SCL open drain and
// feed it back through scl_in. sda_out is always zero; sda_out_en pulls SDA low.
// Do not connect scl directly to a push-pull board output.
//
// ACK errors: 1=device write, 2=register low, 3=register high, 4=data write,
// 5=device read. E=unsupported request/configuration. F=timeout/bus held low.
// NACK ends with STOP; timeout releases both pins (a held-low bus cannot be
// forced to STOP). Faults are sticky until rstn. No failed request emits
// byte_over. A wrapper MUST gate/reset its sequencer on transaction_failed,
// since busy eventually falls on both success and failure.
//
// FSM follows rtl/reg16_i2c.v, with request compatibility, success-only
// completion, separate open-drain controls, and post-STOP bus-release checking.
// T_WR retains the vendor driver's actual MICROSECOND delay convention.
module iic_dri_checked #(
    parameter CLK_FRE=27'd50_000_000,
    parameter IIC_FREQ=20'd400_000,
    parameter T_WR=10'd5,
    parameter ADDR_BYTE=2'd2,
    parameter LEN_WIDTH=8'd3,
    parameter DATA_BYTE=2'd1,
    parameter TIMEOUT_CYCLES=CLK_FRE/100
)(
    input clk, input rstn, input pluse,
    input [7:0] device_id,
    input w_r,
    input [LEN_WIDTH:0] byte_len,
    input [ADDR_BYTE*8-1:0] addr,
    input [7:0] data_in,
    output reg busy,
    output reg byte_over,
    output reg [7:0] data_out,
    output scl,
    input scl_in,
    input sda_in,
    output sda_out,
    output sda_out_en,
    output reg transaction_failed,
    output reg [3:0] error_code
);
    localparam [63:0] DIVISOR=(IIC_FREQ>0) ? 64'd4*IIC_FREQ : 64'd1;
    localparam [63:0] REQUEST_QUARTER=(CLK_FRE+DIVISOR-1)/DIVISOR;
    // NXP UM10204 rev7 table11: fast tLOW>=1.3us and START/STOP
    // setup/hold>=0.6us. Standard-mode uses a conservative 4.7us
    // quarter for START/STOP/bus-free. Physical high phases also wait
    // for synchronized SCL; IIC_FREQ is an upper bound, not exact rate.
    localparam [63:0] MIN_QUARTER=(IIC_FREQ<=100_000)
        ? (CLK_FRE*64'd47+64'd9_999_999)/64'd10_000_000
        : (CLK_FRE*64'd13+64'd19_999_999)/64'd20_000_000;
    localparam TIMED_QUARTER=(REQUEST_QUARTER>MIN_QUARTER) ? REQUEST_QUARTER : MIN_QUARTER;
    localparam QUARTER_CYCLES=(TIMED_QUARTER<3) ? 3 : TIMED_QUARTER;
    localparam [63:0] WR_DELAY=(CLK_FRE*64'd1*T_WR+64'd999_999)/64'd1_000_000;
    localparam COMPLETE_DELAY=(WR_DELAY<2) ? 2 : WR_DELAY;
    localparam IDLE=0, START0=1, START1=2, TX0=3, TX1=4, TX2=5, TX3=6,
        ACK0=7, ACK1=8, ACK2=9, ACK3=10, RE0=11, RE1=12, RE2=13,
        RX0=14, RX1=15, RX2=16, RX3=17, NACK0=18, NACK1=19,
        NACK2=20, NACK3=21, STOP0=22, STOP1=23, STOP2=24,
        BUS_FREE=25, SUCCESS_HOLD=26;
    reg [4:0] state;
    reg scl_low, sda_low;
    assign scl=!scl_low;
    assign sda_out=1'b0;
    assign sda_out_en=sda_low;
    (* async_reg = "true" *) reg scl_meta, scl_sampled, sda_meta, sda_sampled;
    reg pluse_1d, pluse_2d, pluse_3d;
    always @(posedge clk or negedge rstn) begin
        if(!rstn) begin
            scl_meta<=1; scl_sampled<=1; sda_meta<=1; sda_sampled<=1;
            pluse_1d<=0; pluse_2d<=0; pluse_3d<=0;
        end else begin
            scl_meta<=scl_in; scl_sampled<=scl_meta;
            sda_meta<=sda_in; sda_sampled<=sda_meta;
            pluse_1d<=pluse; pluse_2d<=pluse_1d; pluse_3d<=pluse_2d;
        end
    end
    reg [31:0] divider, watchdog, complete_count;
    reg [7:0] dev, tx, write_data, read_data;
    reg [15:0] register_addr;
    reg is_read, nack;
    reg [2:0] bit_index, byte_index;
    reg [3:0] pending_error;
    // High phases wait for actual SCL, including synchronizer settling.
    wire stretch=!scl_low && !scl_sampled;
    wire invalid_request=(ADDR_BYTE!=2) || (DATA_BYTE!=1) || (byte_len!=1)
        || (IIC_FREQ<=0) || (IIC_FREQ>400_000) || (CLK_FRE<DIVISOR)
        || (CLK_FRE<1) || (CLK_FRE>100_000_000) || (T_WR<0)
        || (TIMEOUT_CYCLES<1) || (TIMEOUT_CYCLES>64'hffff_ffff)
        || (WR_DELAY>64'hffff_ffff);
    always @(posedge clk or negedge rstn) begin
        if(!rstn) begin
            state<=IDLE; busy<=0; byte_over<=0; data_out<=0;
            transaction_failed<=0; error_code<=0; pending_error<=0;
            scl_low<=0; sda_low<=0; divider<=0; watchdog<=0; complete_count<=0;
            dev<=0; tx<=0; write_data<=0; read_data<=0; register_addr<=0;
            is_read<=0; nack<=0; bit_index<=7; byte_index<=0;
        end else begin
            byte_over<=0;
            if(state==IDLE) begin
                busy<=0; divider<=0; watchdog<=0; scl_low<=0; sda_low<=0;
                if(pluse_2d && !pluse_3d && !transaction_failed) begin
                    if(invalid_request) begin
                        transaction_failed<=1; error_code<=4'he;
                    end else begin
                        busy<=1; pending_error<=0; complete_count<=0;
                        dev<=device_id; register_addr<=addr;
                        write_data<=data_in; read_data<=0; is_read<=!w_r;
                        tx<={device_id[7:1],1'b0}; bit_index<=7; byte_index<=0;
                        state<=START0;
                    end
                end
            end else if(state==SUCCESS_HOLD) begin
                // Keep byte_over ahead of busy falling, as MS72xx tables use
                // it to advance their command index before the next request.
                if(complete_count==COMPLETE_DELAY-1) begin
                    busy<=0; state<=IDLE;
                end else complete_count<=complete_count+1;
            end else if(watchdog>=TIMEOUT_CYCLES-1) begin
                scl_low<=0; sda_low<=0; busy<=0;
                transaction_failed<=1; error_code<=4'hf; state<=IDLE;
            end else begin
                watchdog<=watchdog+1;
                if(stretch || ((state==START0 || state==BUS_FREE) && !sda_sampled)) divider<=0;
                else if(divider==QUARTER_CYCLES-1) begin
                    divider<=0;
                    case(state)
                        START0: begin sda_low<=1; state<=START1; end
                        START1: begin scl_low<=1; state<=TX0; end
                        TX0: begin sda_low<=!tx[bit_index]; state<=TX1; end
                        TX1: begin scl_low<=0; state<=TX2; end
                        TX2: begin
                            // A released transmit bit must actually be high.
                            // This is a single-master bus; conflicting low is
                            // a bus fault, not a byte that may succeed.
                            if(tx[bit_index] && !sda_sampled) begin
                                scl_low<=0; sda_low<=0; busy<=0;
                                transaction_failed<=1; error_code<=4'hf; state<=IDLE;
                            end else state<=TX3;
                        end
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
                            if(nack) begin
                                pending_error<=(is_read && byte_index==3) ? 4'd5 : {1'b0,byte_index}+1'b1;
                                state<=STOP0;
                            end else case(byte_index)
                                0: begin tx<=register_addr[7:0]; byte_index<=1; state<=TX0; end
                                1: begin tx<=register_addr[15:8]; byte_index<=2; state<=TX0; end
                                2: begin
                                    byte_index<=3;
                                    if(is_read) begin tx<={dev[7:1],1'b1}; state<=RE0; end
                                    else begin tx<=write_data; state<=TX0; end
                                end
                                3: state<=is_read ? RX0 : STOP0;
                                default: begin pending_error<=4'he; state<=STOP0; end
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
                        STOP2: begin sda_low<=0; state<=BUS_FREE; end
                        BUS_FREE: begin
                            if(pending_error!=0) begin
                                transaction_failed<=1; error_code<=pending_error;
                                busy<=0; state<=IDLE;
                            end else begin
                                if(is_read) data_out<=read_data;
                                byte_over<=1; complete_count<=0; state<=SUCCESS_HOLD;
                            end
                        end
                        default: begin
                            scl_low<=0; sda_low<=0; busy<=0;
                            transaction_failed<=1; error_code<=4'he; state<=IDLE;
                        end
                    endcase
                end else divider<=divider+1;
            end
        end
    end
endmodule
