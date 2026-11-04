`timescale 1ns/1ps
// Optional framed UART demux. Active legacy protocols SGA1/SGT1/SGF1 are
// fixed24B and forwarded byte-exact. SGR1 is fixed36B and never forwarded.
// Prefix replay takes at most4 ctrl clocks; physical UART bytes are separated
// by10*BIT_CYCLES. Unknown bytes are preserved; unknown future packet payloads
// do not gain a framing guarantee until their magic/length is registered here.
module uart_rotation_router #(parameter integer BYTE_TIMEOUT_CYCLES=2700000)(
 input wire clk,rst_n,rx_valid,rx_error,input wire [7:0] rx_data,
 input wire [31:0] base_param_id,
 output reg arm_rx_valid,arm_rx_error,output reg [7:0] arm_rx_data,
 output reg config_valid,input wire config_ready,output reg [127:0] config_data,
 output reg [31:0] config_queued,config_rejected,config_busy_drops,route_overruns
);
 reg [287:0] packet;
 reg [31:0] crc,param_crc,age,replay_data;
 reg [23:0] prefix;
 reg [2:0] prefix_count,replay_len,replay_index;
 reg [5:0] count;
 reg is_rotation;
 wire signed [31:0] packet_cos=$signed(packet[160+:32]);
 wire signed [31:0] packet_sin=$signed(packet[192+:32]);
 wire schema_ok=packet[32+:8]==1&&packet[40+:8]==1&&packet[48+:16]==36&&
  packet[64+:32]!=0&&packet[96+:32]==base_param_id&&packet[224+:32]==~param_crc&&
  packet_cos>=-32'sd1073741824&&packet_cos<=32'sd1073741824&&
  packet_sin>=-32'sd1073741824&&packet_sin<=32'sd1073741824&&(packet_cos!=0||packet_sin!=0);
 function automatic [31:0] crc_byte(input [31:0] c0,input [7:0] b);
  reg [31:0] c;integer k;begin c=c0^b;for(k=0;k<8;k=k+1)c=c[0]?(c>>1)^32'hedb88320:c>>1;crc_byte=c;end
 endfunction
 function automatic [31:0] inc(input [31:0] n);inc=(&n)?n:n+1'b1;endfunction
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin
   packet<=0;crc<=32'hffffffff;param_crc<=32'hffffffff;age<=0;
   prefix<=0;prefix_count<=0;replay_data<=0;replay_len<=0;replay_index<=0;count<=0;is_rotation<=0;
   arm_rx_valid<=0;arm_rx_error<=0;arm_rx_data<=0;config_valid<=0;config_data<=0;
   config_queued<=0;config_rejected<=0;config_busy_drops<=0;route_overruns<=0;
  end else begin
   arm_rx_valid<=0;arm_rx_error<=0;
   if(config_valid&&config_ready)config_valid<=0;
   if(replay_len!=0)begin
    arm_rx_valid<=1;arm_rx_data<=replay_data[replay_index*8+:8];
    if(replay_index+1>=replay_len)begin replay_len<=0;replay_index<=0;end
    else replay_index<=replay_index+1'b1;
    if(rx_valid||rx_error)route_overruns<=inc(route_overruns);
   end else if(rx_error)begin
    if(count!=0&&is_rotation)config_rejected<=inc(config_rejected);else arm_rx_error<=1;
    prefix<=0;prefix_count<=0;count<=0;age<=0;crc<=32'hffffffff;param_crc<=32'hffffffff;
   end else if(rx_valid)begin
    age<=0;
    if(count!=0)begin
     if(!is_rotation)begin
      arm_rx_valid<=1;arm_rx_data<=rx_data;
      if(count==23)begin count<=0;prefix_count<=0;prefix<=0;end else count<=count+1'b1;
     end else begin
      packet[count*8+:8]<=rx_data;
      if(count<32)crc<=crc_byte(crc,rx_data);
      if(count>=12&&count<28)param_crc<=crc_byte(param_crc,rx_data);
      if(count==35)begin
       count<=0;prefix_count<=0;prefix<=0;
       if({rx_data,packet[256+:24]}!=~crc||!schema_ok)config_rejected<=inc(config_rejected);
       else if(config_valid&&!config_ready)config_busy_drops<=inc(config_busy_drops);
       else begin
        config_data<={packet[224+:32],packet[128+:32],packet[160+:32],packet[192+:32]};
        config_valid<=1;config_queued<=inc(config_queued);
       end
      end else count<=count+1'b1;
     end
    end else case(prefix_count)
     0:if(rx_data==8'h53)begin prefix<=24'h000053;prefix_count<=1;end
       else begin arm_rx_valid<=1;arm_rx_data<=rx_data;end
     1:if(rx_data==8'h47)begin prefix<=24'h004753;prefix_count<=2;end
       else if(rx_data==8'h53)begin replay_data<=32'h00000053;replay_len<=1;replay_index<=0;prefix<=24'h53;prefix_count<=1;end
       else begin replay_data<={16'd0,rx_data,8'h53};replay_len<=2;replay_index<=0;prefix<=0;prefix_count<=0;end
     2:if(rx_data==8'h41||rx_data==8'h52||rx_data==8'h54||rx_data==8'h46)begin prefix<={rx_data,16'h4753};prefix_count<=3;end
       else if(rx_data==8'h53)begin replay_data<=32'h00004753;replay_len<=2;replay_index<=0;prefix<=24'h53;prefix_count<=1;end
       else begin replay_data<={8'd0,rx_data,16'h4753};replay_len<=3;replay_index<=0;prefix<=0;prefix_count<=0;end
     3:if(rx_data==8'h31)begin
        prefix_count<=0;count<=4;packet[31:0]<={rx_data,prefix};
        is_rotation<=prefix[23:16]==8'h52;
        if(prefix[23:16]==8'h52)begin
         crc<=crc_byte(crc_byte(crc_byte(crc_byte(32'hffffffff,8'h53),8'h47),8'h52),8'h31);
         param_crc<=32'hffffffff;
        end else begin replay_data<={rx_data,prefix};replay_len<=4;replay_index<=0;end
       end else if(rx_data==8'h53)begin replay_data<={8'd0,prefix};replay_len<=3;replay_index<=0;prefix<=24'h53;prefix_count<=1;end
       else begin replay_data<={rx_data,prefix};replay_len<=4;replay_index<=0;prefix<=0;prefix_count<=0;end
     default:begin prefix<=0;prefix_count<=0;end
    endcase
   end else if(count!=0||prefix_count!=0)begin
    if(age>=BYTE_TIMEOUT_CYCLES-1)begin
     if(count!=0&&is_rotation)config_rejected<=inc(config_rejected);
     // A timed-out partial prefix must not restart the legacy parser's age.
     if(count==0&&prefix_count!=0)arm_rx_error<=1;
     count<=0;prefix_count<=0;prefix<=0;age<=0;crc<=32'hffffffff;param_crc<=32'hffffffff;
    end else age<=age+1'b1;
   end
  end
 end
endmodule
