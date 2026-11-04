`timescale 1ns/1ps
// Measurement profile only: SGA1 and SGT1 are both fixed 24-byte packets.
// Route complete framing, including magic, to the unchanged validating parser.
// A four-byte elastic prefix queue also accepts one input byte every clock.
module measurement_rx_router #(parameter integer BYTE_TIMEOUT_CYCLES=2700000)(
    input wire clk,rst_n,rx_valid,rx_error,input wire [7:0] rx_data,
    output reg arm_rx_valid,arm_rx_error,output reg [7:0] arm_rx_data,
    output reg stats_rx_valid,stats_rx_error,output reg [7:0] stats_rx_data
);
    reg [31:0] search,age;
    reg [4:0] count;
    reg packet_stats;
    reg [8:0] pending[0:3];
    reg [1:0] read_ptr,write_ptr;
    reg [2:0] used;
    wire pop=used!=0;
    wire [31:0] next_search={rx_data,search[31:8]};
    wire found_arm=next_search==32'h31414753;
    wire found_stats=next_search==32'h31544753;
    integer i;
    always @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin
            search<=0;age<=0;count<=0;packet_stats<=0;
            read_ptr<=0;write_ptr<=0;used<=0;
            arm_rx_valid<=0;arm_rx_error<=0;arm_rx_data<=0;
            stats_rx_valid<=0;stats_rx_error<=0;stats_rx_data<=0;
        end else begin
            arm_rx_valid<=0;arm_rx_error<=0;stats_rx_valid<=0;stats_rx_error<=0;
            used<=used-pop;
            if(pop)begin
                read_ptr<=read_ptr+1'b1;
                if(pending[read_ptr][8])begin
                    stats_rx_valid<=1;stats_rx_data<=pending[read_ptr][7:0];
                end else begin
                    arm_rx_valid<=1;arm_rx_data<=pending[read_ptr][7:0];
                end
            end
            if(rx_error)begin
                // A physical framing loss invalidates any partial command.
                search<=0;age<=0;count<=0;used<=0;read_ptr<=0;write_ptr<=0;
                arm_rx_valid<=0;stats_rx_valid<=0;arm_rx_error<=1;stats_rx_error<=1;
            end else if(rx_valid)begin
                age<=0;
                if(count==0)begin
                    search<=next_search;
                    if(found_arm || found_stats)begin
                        // Both current parsers consume exactly24 bytes even when
                        // the received length/schema/CRC is invalid. Do not trust
                        // packet length or search for magic inside its payload.
                        for(i=0;i<4;i=i+1)
                            pending[(write_ptr+i)&3]<={found_stats,next_search[i*8+:8]};
                        used<=used-pop+4;
                        count<=4;packet_stats<=found_stats;search<=0;
                    end
                end else begin
                    pending[write_ptr]<={packet_stats,rx_data};
                    write_ptr<=write_ptr+1'b1;used<=used-pop+1;
                    if(count==23)begin count<=0;search<=0;end
                    else count<=count+1'b1;
                end
            end else if(count!=0 || search!=0)begin
                if(age>=BYTE_TIMEOUT_CYCLES-1)begin
                    // Reset the selected original parser before accepting a new
                    // packet; do not leave its delayed prefix collecting bytes.
                    if(count!=0)begin
                        if(packet_stats)stats_rx_error<=1;else arm_rx_error<=1;
                    end
                    search<=0;age<=0;count<=0;used<=0;read_ptr<=0;write_ptr<=0;
                    arm_rx_valid<=0;stats_rx_valid<=0;
                end else age<=age+1'b1;
            end
        end
    end
endmodule
