`timescale 1ns/1ps
// Independent 27 MHz diagnostic UART. PGIQ0001,84 bytes,CRC32 over first80.
// first/follow flags distinguish immutable fault snapshots from live readout.
module hdmi_input_runtime_diag_uart #(
 parameter integer GAP_CLKS=6750000,MAX_PACKETS=240,CLOCK_HZ=27000000,BAUD=115200
)(input wire clk_27m,first_valid,follow_valid,uptime_wrapped,
 input wire [255:0] first_tuple,follow_tuple,live_tuple,output wire telemetry_tx);
 reg [1:0] release_pipe=0;
 always @(posedge clk_27m)release_pipe<={release_pipe[0],1'b1};
 wire local_rst_n=release_pipe[1];
 reg [31:0] gap_count=0,packet_count=0;
 reg [7:0] byte_index=0,tx_data=0;
 reg [639:0] held_payload=0;
 reg [31:0] packet_crc=32'hffffffff;
 reg active=0,tx_start=0;wire tx_busy,tx_done;
 function [31:0] crc_byte(input [31:0] c0,input [7:0] d);
  integer j;reg [31:0] c;begin c=c0^d;for(j=0;j<8;j=j+1)c=c[0] ? ((c>>1)^32'hedb88320):(c>>1);crc_byte=c;end
 endfunction
 function [7:0] marker(input [7:0] n);
  begin if(n<80)marker=held_payload[n*8+:8];
   else case(n)80:marker=~packet_crc[7:0];81:marker=~packet_crc[15:8];
    82:marker=~packet_crc[23:16];83:marker=~packet_crc[31:24];default:marker=0;endcase
  end
 endfunction
 always @(posedge clk_27m)begin
  if(!local_rst_n)begin gap_count<=0;packet_count<=0;byte_index<=0;held_payload<=0;
   packet_crc<=32'hffffffff;active<=0;tx_start<=0;tx_data<=0;end
  else begin
   tx_start<=0;
   if(!active && packet_count<MAX_PACKETS)begin
    if(gap_count==GAP_CLKS-1)begin
     gap_count<=0;byte_index<=0;active<=1;
     held_payload[63:0]<=64'h3130303051494750;
     held_payload[71:64]<={5'b0,uptime_wrapped,follow_valid,first_valid};
     held_payload[79:72]<=8'd84;held_payload[95:80]<=0;
     held_payload[127:96]<=packet_count;
     held_payload[383:128]<=first_valid ? first_tuple:live_tuple;
     held_payload[639:384]<=follow_valid ? follow_tuple:live_tuple;
     packet_crc<=32'hffffffff;
    end else gap_count<=gap_count+1'b1;
   end
   if(active && tx_done)begin
    if(byte_index==83)begin active<=0;packet_count<=packet_count+1'b1;end
    else byte_index<=byte_index+1'b1;
   end
   if(active && !tx_busy && !tx_start && !tx_done)begin
    tx_data<=marker(byte_index);tx_start<=1;
    if(byte_index<80)packet_crc<=crc_byte(packet_crc,marker(byte_index));
   end
  end
 end
 uart_tx #(.CLOCK_HZ(CLOCK_HZ),.BAUD(BAUD)) beacon(.clk(clk_27m),.rst_n(local_rst_n),
  .start(tx_start),.data(tx_data),.tx(telemetry_tx),.busy(tx_busy),.done(tx_done));
endmodule
