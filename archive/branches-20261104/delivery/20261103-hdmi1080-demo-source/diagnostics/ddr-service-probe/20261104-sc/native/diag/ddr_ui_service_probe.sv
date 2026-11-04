`timescale 1ns/1ps
// Isolated single-outstanding Pango UI service probe; NOT a frame pipeline.
// UI units=4B, data=256b, no B/RREADY. AP belongs to the future top (tie 0).
// Each successful run writes 8 banks x 2 rows x 16 beats = 8192 bytes, then
// reads three patterns. Success is finite and idle. A failed unaccepted AW/AR
// MUST remain valid until accepted, then its transaction is drained/quarantined;
// an unresponsive bus therefore needs the parent's coordinated reset.
module ddr_ui_service_probe #(
 parameter READS_PER_GROUP=16,TIMEOUT_CYCLES=4096,GAP_CYCLES=8
)(
 input clk,rst_n,init_done,
 output [27:0] awaddr,araddr,output [3:0] awlen,arlen,
 output awvalid,arvalid,input awready,arready,
 output [255:0] wdata,output [31:0] wstrb,input wready,wlast,
 input [255:0] rdata,input rvalid,rlast,input [3:0] rid,
 output reg started,done,failed,output reg [7:0] fault,
 output [3:0] phase,output [1:0] active_group,
 output reg [31:0] writes,reads,read_beats,data_error_beats,protocol_errors,timeouts,crc_error_groups,
 output reg [95:0] group_count,
 output reg [95:0] ar_wait_min,ar_wait_max,ar_wait_sum,
 output reg [95:0] first_min,first_max,first_sum,
 output reg [95:0] last_min,last_max,last_sum,
 output [95:0] actual_crc,expected_crc
);
 localparam WAIT_INIT=0,WADDR=1,WSTREAM=2,WGAP=3,RADDR=4,RSTREAM=5,RGAP=6,FINISH=7,QUARANTINE=8;
 reg [3:0] state;
 reg [3:0] write_location,beat;
 reg [1:0] group_id;
 reg [31:0] read_index,tick,address_tick,first_this,wait_this,wait_counter,watchdog,gap;
 reg first_seen;
 reg [95:0] crc_a,crc_e;
 wire [2:0] write_bank=write_location[3:1];
 wire write_row=write_location[0];
 wire [2:0] read_bank=group_id==2 ? read_index[2:0]:3'd0;
 wire read_row=group_id==1 ? read_index[0]:1'b0;
 assign awaddr={write_bank,15'd0,10'd0}+ (write_row ? 28'd1024:28'd0);
 assign araddr={read_bank,15'd0,10'd0}+ (read_row ? 28'd1024:28'd0);
 assign awlen=4'd15;assign arlen=4'd15;assign wstrb=32'hffffffff;
 assign awvalid=state==WADDR;assign arvalid=state==RADDR;
 assign phase=state;assign active_group=group_id;
 assign actual_crc=~crc_a;assign expected_crc=~crc_e;
 wire accept_w=state==WADDR && awready;
 wire accept_r=state==RADDR && arready;
 wire transfer_w=(state==WSTREAM || accept_w) && wready;
 wire transfer_r=(state==RSTREAM || accept_r) && rvalid;
 wire end_w=transfer_w && beat==15;
 wire end_r=transfer_r && (beat==15 || rlast);
 wire active=state==WADDR || state==WSTREAM || state==RADDR || state==RSTREAM;
 wire [31:0] elapsed=tick-(accept_r ? tick:address_tick);
 function [255:0] pattern(input [27:0] base,input [3:0] index);
  integer lane;reg [27:0] a;
  begin
   for(lane=0;lane<8;lane=lane+1)begin
    a=base+index*8+lane;pattern[lane*32+:32]={4'ha,a} ^ 32'h6a09e667;
   end
  end
 endfunction
 function [31:0] crc_word(input [31:0] seed,input [255:0] word);
  reg [31:0] c;integer j,k;
  begin c=seed;for(j=0;j<32;j=j+1)begin
   c=c ^ word[j*8+:8];for(k=0;k<8;k=k+1)c=c[0] ? (c>>1)^32'hedb88320:c>>1;
  end crc_word=c;end
 endfunction
 assign wdata=pattern(awaddr,beat);
 wire [255:0] expected_data=pattern(araddr,beat);
 wire [31:0] next_crc_a=crc_word(crc_a[group_id*32+:32],rdata);
 wire [31:0] next_crc_e=crc_word(crc_e[group_id*32+:32],expected_data);
 wire bad_r_protocol=(rid!==4'd0) || (rlast!==(beat==15));
 wire bad_data=rdata!==expected_data;
 wire bad_group_crc=transfer_r && beat==15 && read_index==READS_PER_GROUP-1 && next_crc_a!==next_crc_e;
 integer g;
 always @(posedge clk)begin
  if(!rst_n)begin
   state<=WAIT_INIT;started<=0;done<=0;failed<=0;fault<=0;
   write_location<=0;beat<=0;group_id<=0;read_index<=0;tick<=0;address_tick<=0;
   first_this<=0;wait_this<=0;wait_counter<=0;watchdog<=0;gap<=0;first_seen<=0;
   writes<=0;reads<=0;read_beats<=0;data_error_beats<=0;protocol_errors<=0;timeouts<=0;crc_error_groups<=0;
   group_count<=0;ar_wait_min<={96{1'b1}};ar_wait_max<=0;ar_wait_sum<=0;
   first_min<={96{1'b1}};first_max<=0;first_sum<=0;
   last_min<={96{1'b1}};last_max<=0;last_sum<=0;
   crc_a<={96{1'b1}};crc_e<={96{1'b1}};
  end else begin
   if(started)tick<=tick+1'b1;
   if(active && !failed)watchdog<=watchdog+1'b1;else watchdog<=0;
   if(active && !failed && watchdog==TIMEOUT_CYCLES-1 && !end_w && !end_r)begin
    failed<=1;fault<=8'h01;timeouts<=timeouts+1'b1;
   end
   if(started && !failed && !init_done)begin failed<=1;fault<=8'h07;end
   if(state==RADDR && !arready)wait_counter<=wait_counter+1'b1;
   if(accept_r)begin address_tick<=tick;wait_this<=wait_counter;first_seen<=0;state<=RSTREAM;end
   if(accept_w)state<=WSTREAM;
   case(state)
    WAIT_INIT:if(init_done && !started)begin started<=1;state<=WADDR;watchdog<=0;end
    WGAP:if(failed || !init_done)state<=QUARANTINE;
     else if(gap==GAP_CYCLES)begin
      gap<=0;beat<=0;watchdog<=0;
      if(write_location==15)begin state<=RADDR;wait_counter<=0;end
      else begin write_location<=write_location+1'b1;state<=WADDR;end
     end else gap<=gap+1'b1;
    RGAP:if(failed || !init_done)state<=QUARANTINE;
     else if(gap==GAP_CYCLES)begin
      gap<=0;beat<=0;watchdog<=0;wait_counter<=0;first_seen<=0;
      if(read_index==READS_PER_GROUP-1)begin
       if(group_id==2)begin state<=FINISH;done<=1;end
       else begin group_id<=group_id+1'b1;read_index<=0;state<=RADDR;end
      end else begin read_index<=read_index+1'b1;state<=RADDR;end
     end else gap<=gap+1'b1;
    FINISH:state<=FINISH;
    QUARANTINE:state<=QUARANTINE;
   endcase
   if(transfer_w)begin
    if(wlast!==(beat==15))begin
     protocol_errors<=protocol_errors+1'b1;
     if(!failed)begin failed<=1;fault<=8'h02;end
    end
    if(beat==15)begin
     writes<=writes+1'b1;beat<=0;watchdog<=0;gap<=0;
     state<=failed || wlast!==1'b1 ? QUARANTINE:WGAP;
    end else beat<=beat+1'b1;
   end
   if(transfer_r)begin
    read_beats<=read_beats+1'b1;
    crc_a[group_id*32+:32]<=next_crc_a;crc_e[group_id*32+:32]<=next_crc_e;
    if(!first_seen || accept_r)begin first_seen<=1;first_this<=elapsed;end
    if(bad_r_protocol)begin
     protocol_errors<=protocol_errors+1'b1;
     if(!failed)begin failed<=1;fault<=8'h03;end
    end
    if(bad_data)begin
     data_error_beats<=data_error_beats+1'b1;
     if(!failed && !bad_r_protocol)begin failed<=1;fault<=8'h05;end
    end
    if(end_r)begin
     if(bad_group_crc)begin
      crc_error_groups<=crc_error_groups+1'b1;
      if(!failed && !bad_r_protocol && !bad_data)begin failed<=1;fault<=8'h06;end
     end
     beat<=0;watchdog<=0;gap<=0;
     if(failed || bad_r_protocol || bad_data || bad_group_crc)state<=QUARANTINE;
     else begin
      state<=RGAP;reads<=reads+1'b1;
      group_count[group_id*32+:32]<=group_count[group_id*32+:32]+1'b1;
      if(wait_this<ar_wait_min[group_id*32+:32])ar_wait_min[group_id*32+:32]<=wait_this;
      if(wait_this>ar_wait_max[group_id*32+:32])ar_wait_max[group_id*32+:32]<=wait_this;
      ar_wait_sum[group_id*32+:32]<=ar_wait_sum[group_id*32+:32]+wait_this;
      if(first_this<first_min[group_id*32+:32])first_min[group_id*32+:32]<=first_this;
      if(first_this>first_max[group_id*32+:32])first_max[group_id*32+:32]<=first_this;
      first_sum[group_id*32+:32]<=first_sum[group_id*32+:32]+first_this;
      if(elapsed<last_min[group_id*32+:32])last_min[group_id*32+:32]<=elapsed;
      if(elapsed>last_max[group_id*32+:32])last_max[group_id*32+:32]<=elapsed;
      last_sum[group_id*32+:32]<=last_sum[group_id*32+:32]+elapsed;
     end
    end else beat<=beat+1'b1;
   end
   if(started && !failed && ((rvalid && !transfer_r)||(wready && !transfer_w)))begin
    protocol_errors<=protocol_errors+1'b1;failed<=1;fault<=8'h04;
    if(!active)state<=QUARANTINE;
   end
  end
 end
 initial begin
  if(READS_PER_GROUP<8 || READS_PER_GROUP>1024 || TIMEOUT_CYCLES<32 || TIMEOUT_CYCLES>65536 || GAP_CYCLES<0 || GAP_CYCLES>1024)
   $error("invalid DDR probe parameters");
 end
endmodule
