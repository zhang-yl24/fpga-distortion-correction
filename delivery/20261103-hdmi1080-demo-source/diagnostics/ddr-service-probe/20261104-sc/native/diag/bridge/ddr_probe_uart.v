`timescale 1ns/1ps
// Same byte-start/done and CRC mechanism as the verified cfg_probe_uart.
module ddr_probe_uart #(
 parameter integer GAP_CLKS=6750000,MAX_PACKETS=120,CLOCK_HZ=27000000,BAUD=115200
)(
 input clk,rst_n,epoch_run,input[3:0] live_flags,
 input snapshot_valid,input[1183:0] snapshot,
 output tx,output reg latest_valid=0
);
 reg[31:0]uptime=0,snapshot_count=0,snapshot_age=32'hffffffff;
 reg[1183:0]latest=0;reg[31:0]gap_count=0;
 reg[7:0]packet_count=0;reg[1:0]group_index=0;reg[6:0]byte_index=0;
 reg[607:0]held_payload=0;reg[31:0]packet_crc=32'hffffffff;
 reg active=0,tx_start=0;reg[7:0]tx_data=0;wire tx_busy,tx_done;
 localparam[383:0]EMPTY_GROUP={32'd0,32'd0,32'd0,32'd0,32'hffffffff,32'd0,32'd0,32'hffffffff,32'd0,32'd0,32'hffffffff,32'd0};
 wire incoming=epoch_run && snapshot_valid;
 wire have_packet=epoch_run && (incoming || latest_valid);
 wire[1183:0]packet_snapshot=incoming ? snapshot:latest;
 wire[383:0]packet_group=have_packet ? packet_snapshot[group_index*384+:384]:EMPTY_GROUP;
 function[31:0]crc_byte(input[31:0]crc,input[7:0]data);
  reg[31:0]c;integer i;begin c=crc^data;for(i=0;i<8;i=i+1)c=c[0] ? (c>>1)^32'hedb88320:c>>1;crc_byte=c;end
 endfunction
 function[7:0]marker(input[6:0]n);
  begin if(n<76)marker=held_payload[n*8+:8];else case(n)
   76:marker=~packet_crc[7:0];77:marker=~packet_crc[15:8];78:marker=~packet_crc[23:16];79:marker=~packet_crc[31:24];default:marker=0;
  endcase end
 endfunction
 always @(posedge clk)begin
  if(!rst_n)begin uptime<=0;snapshot_count<=0;snapshot_age<=32'hffffffff;latest<=0;latest_valid<=0;end
  else begin
   uptime<=uptime+1'b1;
   if(!epoch_run)begin snapshot_count<=0;snapshot_age<=32'hffffffff;latest<=0;latest_valid<=0;end
   else if(incoming)begin latest<=snapshot;latest_valid<=1;snapshot_count<=snapshot_count+1'b1;snapshot_age<=0;end
   else if(snapshot_age!=32'hffffffff)snapshot_age<=snapshot_age+1'b1;
  end
 end
 always @(posedge clk)begin
  if(!rst_n)begin gap_count<=0;packet_count<=0;group_index<=0;byte_index<=0;held_payload<=0;packet_crc<=32'hffffffff;active<=0;tx_start<=0;tx_data<=0;end
  else begin
   tx_start<=0;
   if(!active && packet_count<MAX_PACKETS)begin
    if(gap_count==GAP_CLKS-1)begin
     gap_count<=0;byte_index<=0;active<=1;
     held_payload[63:0]<=64'h3130305244444750;
     held_payload[71:64]<=8'd80;held_payload[79:72]<=8'd1;
     held_payload[87:80]<={1'b0,live_flags,have_packet,group_index};held_payload[95:88]<=packet_count;
     held_payload[127:96]<=uptime;
     held_payload[159:128]<=epoch_run ? snapshot_count+(incoming ? 1'b1:1'b0):32'd0;
     held_payload[191:160]<=have_packet ? (incoming ? 32'd0:snapshot_age):32'hffffffff;
     held_payload[575:192]<=packet_group;
     held_payload[607:576]<=have_packet ? packet_snapshot[1183:1152]:32'd0;
     packet_crc<=32'hffffffff;
    end else gap_count<=gap_count+1'b1;
   end
   if(active && tx_done)begin
    if(byte_index==79)begin active<=0;packet_count<=packet_count+1'b1;group_index<=group_index==2 ? 0:group_index+1'b1;end
    else byte_index<=byte_index+1'b1;
   end
   if(active && !tx_busy && !tx_start && !tx_done)begin
    tx_data<=marker(byte_index);tx_start<=1;
    if(byte_index<76)packet_crc<=crc_byte(packet_crc,marker(byte_index));
   end
  end
 end
 uart_tx #(.CLOCK_HZ(CLOCK_HZ),.BAUD(BAUD)) sender(.clk(clk),.rst_n(rst_n),.start(tx_start),.data(tx_data),.tx(tx),.busy(tx_busy),.done(tx_done));
endmodule
