`timescale 1ns/1ps
// EXPERIMENTAL, not integrated into any released camera top.
// Every input must be synchronous to clk. No camera/pixel-domain buses belong
// here. In particular, the existing top's underflows bus is in pix_out_clk:
// version 1 reserves its four bytes as zero and does NOT report underflows.
// status_valid must be zero unless failed/fault are coherent core-domain data.
// A slow UART drops telemetry samples (sequence gaps), never stalls video.
module camera720_core_stats_uart #(
    parameter CLOCK_HZ=125000000,
    parameter BAUD=115200,
    parameter SAMPLE_CYCLES=CLOCK_HZ,
    parameter [63:0] BUILD_ID=64'h0,
    parameter [63:0] PROFILE_ID=64'h0
)(
    input clk, input rst_n,
    input [31:0] source_accepted, processed, unique_presented,
    input status_valid, failed, input [7:0] fault,
    output tx
);
    localparam IDLE=0, CRC=1, SEND=2, WAIT_BYTE=3;
    reg [1:0] state;
    reg [31:0] period_count, sample_sequence;
    reg [63:0] core_ticks;
    reg [479:0] snapshot;
    reg [31:0] crc, packet_crc;
    reg [5:0] byte_index;
    reg uart_start;
    reg [7:0] uart_data;
    wire uart_busy, uart_done;
    wire [7:0] snapshot_byte=snapshot[byte_index*8 +: 8];

    uart_tx #(.CLOCK_HZ(CLOCK_HZ),.BAUD(BAUD)) transmitter(
        .clk(clk),.rst_n(rst_n),.start(uart_start),.data(uart_data),
        .tx(tx),.busy(uart_busy),.done(uart_done));

    function [31:0] crc_byte;
        input [31:0] value;
        input [7:0] data;
        reg [31:0] c;
        integer bit_number;
        begin
            c=value ^ {24'b0,data};
            for(bit_number=0;bit_number<8;bit_number=bit_number+1)
                c=c[0] ? ((c>>1)^32'hedb88320):(c>>1);
            crc_byte=c;
        end
    endfunction

    // The packet is little-endian. Its first 60 bytes are atomically latched
    // on a scheduled edge; ticks describe that edge and counters their values
    // immediately before it, as for any synchronous register observation.
    always @(posedge clk) begin
        if(!rst_n)begin
            state<=IDLE;period_count<=0;sample_sequence<=0;core_ticks<=0;
            snapshot<=0;crc<=32'hffffffff;packet_crc<=0;byte_index<=0;
            uart_start<=0;uart_data<=0;
        end else begin
            core_ticks<=core_ticks+1'b1;
            uart_start<=0;
            if(period_count==SAMPLE_CYCLES-1)begin
                period_count<=0;
                sample_sequence<=sample_sequence+1'b1;
                if(state==IDLE)begin
                    // [0:7] "PGFPS01\n", version, flags, length, sequence,
                    // ticks, three frame counters, unavailable underflows,
                    // fault/reserved, build/profile IDs. CRC follows at 60.
                    snapshot<={PROFILE_ID,BUILD_ID,24'b0,
                        (status_valid ? fault:8'b0),32'b0,
                        unique_presented,processed,source_accepted,
                        (core_ticks+64'd1),sample_sequence,16'd64,
                        {6'b0,status_valid,(status_valid && failed)},8'd1,
                        64'h0a31305350464750};
                    crc<=32'hffffffff;byte_index<=0;state<=CRC;
                end
            end else period_count<=period_count+1'b1;

            case(state)
                CRC: begin
                    crc<=crc_byte(crc,snapshot_byte);
                    if(byte_index==59)begin
                        packet_crc<=crc_byte(crc,snapshot_byte)^32'hffffffff;
                        byte_index<=0;state<=SEND;
                    end else byte_index<=byte_index+1'b1;
                end
                SEND: if(!uart_busy)begin
                    uart_data<=byte_index<60 ? snapshot_byte:
                        (packet_crc >> ((byte_index-60)*8));
                    uart_start<=1;state<=WAIT_BYTE;
                end
                WAIT_BYTE: if(uart_done)begin
                    if(byte_index==63)state<=IDLE;
                    else begin byte_index<=byte_index+1'b1;state<=SEND;end
                end
                default: begin end
            endcase
        end
    end
endmodule
