`timescale 1ns/1ps
// RECOVERY REBUILD, not the lost byte-identical file or its 60-frame evidence.
// Reconstructed from retained Nov5 algorithm/RTL transcript and the public
// stable30 rowburst writer's canonical synchronous lane RAM implementation.
module ddr_tile8_macro_rowburst_writer_run8 #(
 parameter WIDTH=1920,HEIGHT=1080,TAG_W=24,TIMEOUT_BITS=26,
 GROUP_WIDTH=64,MACRO_HEIGHT=32,CRC_FOLD_BITS=1,ENABLE_BLACK_RUN8=0
)(
 input clk,rst_n,input frame_valid,frame_tiled,output frame_ready,
 input [27:0] frame_base,input [31:0] frame_id,
 input in_valid,output in_ready,input [23:0] in_rgb,input [TAG_W-1:0] in_tag,input in_black_run8,
 output [27:0] awaddr,output [3:0] awlen,output awvalid,input awready,
 output [255:0] wdata,output [31:0] wstrb,input wready,wlast,
 output reg done,failed,output reg [7:0] fault,
 output reg [31:0] accepted_pixels,written_beats,last_checksum,completed_id
);
 localparam FRAME_PIXELS=WIDTH*HEIGHT,FRAME_BEATS=FRAME_PIXELS/16;
 localparam MACROS=(HEIGHT+MACRO_HEIGHT-1)/MACRO_HEIGHT;
 localparam FIRST_ROWS=HEIGHT<MACRO_HEIGHT ? HEIGHT:MACRO_HEIGHT;
 localparam TAIL_ROWS=(HEIGHT%MACRO_HEIGHT)==0 ? MACRO_HEIGHT:HEIGHT%MACRO_HEIGHT;
 localparam CRC_ROW_BITS=$clog2(MACRO_HEIGHT);
 localparam GROUP_PIXELS=GROUP_WIDTH*8,ROW_BEATS=GROUP_WIDTH/16;
 localparam ROW_BEAT_LOG=$clog2(ROW_BEATS);
 localparam BEAT_BITS=ROW_BEAT_LOG<1 ? 1:ROW_BEAT_LOG;
 localparam SLOT_BITS=$clog2(GROUP_PIXELS),WORD_ADDR_BITS=$clog2(16*ROW_BEATS);
 localparam TX_IDLE=0,TX_ADDRESS=1,TX_WRITE=2;
 `include "video_crc32.vh"
 function [31:0] crc_zero_run8(input [31:0] c);
 begin
  crc_zero_run8[0]=((((c[0] ^ c[1]) ^ (c[2] ^ (c[3] ^ c[5]))) ^ ((c[9] ^ c[10]) ^ (c[11] ^ (c[12] ^ c[14])))) ^ (((c[15] ^ c[17]) ^ (c[18] ^ (c[22] ^ c[24]))) ^ ((c[25] ^ c[27]) ^ (c[29] ^ (c[30] ^ c[31])))));
  crc_zero_run8[1]=((((c[1] ^ c[2]) ^ (c[3] ^ c[4])) ^ ((c[6] ^ c[10]) ^ (c[11] ^ (c[12] ^ c[13])))) ^ (((c[15] ^ c[16]) ^ (c[18] ^ (c[19] ^ c[23]))) ^ ((c[25] ^ c[26]) ^ (c[28] ^ (c[30] ^ c[31])))));
  crc_zero_run8[2]=((((c[2] ^ c[3]) ^ (c[4] ^ c[5])) ^ ((c[7] ^ c[11]) ^ (c[12] ^ (c[13] ^ c[14])))) ^ (((c[16] ^ c[17]) ^ (c[19] ^ c[20])) ^ ((c[24] ^ c[26]) ^ (c[27] ^ (c[29] ^ c[31])))));
  crc_zero_run8[3]=((((c[3] ^ c[4]) ^ (c[5] ^ c[6])) ^ ((c[8] ^ c[12]) ^ (c[13] ^ c[14]))) ^ (((c[15] ^ c[17]) ^ (c[18] ^ c[20])) ^ ((c[21] ^ c[25]) ^ (c[27] ^ (c[28] ^ c[30])))));
  crc_zero_run8[4]=((((c[0] ^ c[4]) ^ (c[5] ^ c[6])) ^ ((c[7] ^ c[9]) ^ (c[13] ^ (c[14] ^ c[15])))) ^ (((c[16] ^ c[18]) ^ (c[19] ^ c[21])) ^ ((c[22] ^ c[26]) ^ (c[28] ^ (c[29] ^ c[31])))));
  crc_zero_run8[5]=((((c[1] ^ c[5]) ^ (c[6] ^ c[7])) ^ ((c[8] ^ c[10]) ^ (c[14] ^ c[15]))) ^ (((c[16] ^ c[17]) ^ (c[19] ^ c[20])) ^ ((c[22] ^ c[23]) ^ (c[27] ^ (c[29] ^ c[30])))));
  crc_zero_run8[6]=((((c[1] ^ c[3]) ^ (c[5] ^ c[6])) ^ ((c[7] ^ c[8]) ^ (c[10] ^ (c[12] ^ c[14])))) ^ (((c[16] ^ c[20]) ^ (c[21] ^ c[22])) ^ ((c[23] ^ c[25]) ^ (c[27] ^ (c[28] ^ c[29])))));
  crc_zero_run8[7]=((((c[0] ^ c[2]) ^ (c[4] ^ c[6])) ^ ((c[7] ^ c[8]) ^ (c[9] ^ (c[11] ^ c[13])))) ^ (((c[15] ^ c[17]) ^ (c[21] ^ (c[22] ^ c[23]))) ^ ((c[24] ^ c[26]) ^ (c[28] ^ (c[29] ^ c[30])))));
  crc_zero_run8[8]=((((c[0] ^ c[1]) ^ (c[3] ^ (c[5] ^ c[7]))) ^ ((c[8] ^ c[9]) ^ (c[10] ^ (c[12] ^ c[14])))) ^ (((c[16] ^ c[18]) ^ (c[22] ^ (c[23] ^ c[24]))) ^ ((c[25] ^ c[27]) ^ (c[29] ^ (c[30] ^ c[31])))));
  crc_zero_run8[9]=((((c[3] ^ c[4]) ^ (c[5] ^ c[6])) ^ ((c[8] ^ c[12]) ^ (c[13] ^ c[14]))) ^ (((c[18] ^ c[19]) ^ (c[22] ^ c[23])) ^ ((c[26] ^ c[27]) ^ (c[28] ^ c[29]))));
  crc_zero_run8[10]=((((c[1] ^ c[2]) ^ (c[3] ^ c[4])) ^ ((c[6] ^ c[7]) ^ (c[10] ^ (c[11] ^ c[12])))) ^ (((c[13] ^ c[17]) ^ (c[18] ^ (c[19] ^ c[20]))) ^ ((c[22] ^ c[23]) ^ (c[25] ^ (c[28] ^ c[31])))));
  crc_zero_run8[11]=((((c[2] ^ c[3]) ^ (c[4] ^ c[5])) ^ ((c[7] ^ c[8]) ^ (c[11] ^ (c[12] ^ c[13])))) ^ (((c[14] ^ c[18]) ^ (c[19] ^ c[20])) ^ ((c[21] ^ c[23]) ^ (c[24] ^ (c[26] ^ c[29])))));
  crc_zero_run8[12]=((((c[0] ^ c[3]) ^ (c[4] ^ c[5])) ^ ((c[6] ^ c[8]) ^ (c[9] ^ (c[12] ^ c[13])))) ^ (((c[14] ^ c[15]) ^ (c[19] ^ (c[20] ^ c[21]))) ^ ((c[22] ^ c[24]) ^ (c[25] ^ (c[27] ^ c[30])))));
  crc_zero_run8[13]=((((c[1] ^ c[4]) ^ (c[5] ^ c[6])) ^ ((c[7] ^ c[9]) ^ (c[10] ^ (c[13] ^ c[14])))) ^ (((c[15] ^ c[16]) ^ (c[20] ^ (c[21] ^ c[22]))) ^ ((c[23] ^ c[25]) ^ (c[26] ^ (c[28] ^ c[31])))));
  crc_zero_run8[14]=((((c[2] ^ c[5]) ^ (c[6] ^ c[7])) ^ ((c[8] ^ c[10]) ^ (c[11] ^ (c[14] ^ c[15])))) ^ (((c[16] ^ c[17]) ^ (c[21] ^ c[22])) ^ ((c[23] ^ c[24]) ^ (c[26] ^ (c[27] ^ c[29])))));
  crc_zero_run8[15]=((((c[0] ^ c[3]) ^ (c[6] ^ c[7])) ^ ((c[8] ^ c[9]) ^ (c[11] ^ (c[12] ^ c[15])))) ^ (((c[16] ^ c[17]) ^ (c[18] ^ (c[22] ^ c[23]))) ^ ((c[24] ^ c[25]) ^ (c[27] ^ (c[28] ^ c[30])))));
  crc_zero_run8[16]=((((c[2] ^ c[3]) ^ (c[4] ^ c[5])) ^ ((c[7] ^ c[8]) ^ (c[11] ^ (c[13] ^ c[14])))) ^ (((c[15] ^ c[16]) ^ (c[19] ^ c[22])) ^ ((c[23] ^ c[26]) ^ (c[27] ^ (c[28] ^ c[30])))));
  crc_zero_run8[17]=((((c[3] ^ c[4]) ^ (c[5] ^ c[6])) ^ ((c[8] ^ c[9]) ^ (c[12] ^ (c[14] ^ c[15])))) ^ (((c[16] ^ c[17]) ^ (c[20] ^ c[23])) ^ ((c[24] ^ c[27]) ^ (c[28] ^ (c[29] ^ c[31])))));
  crc_zero_run8[18]=((((c[4] ^ c[5]) ^ (c[6] ^ c[7])) ^ ((c[9] ^ c[10]) ^ (c[13] ^ c[15]))) ^ (((c[16] ^ c[17]) ^ (c[18] ^ c[21])) ^ ((c[24] ^ c[25]) ^ (c[28] ^ (c[29] ^ c[30])))));
  crc_zero_run8[19]=((((c[0] ^ c[5]) ^ (c[6] ^ c[7])) ^ ((c[8] ^ c[10]) ^ (c[11] ^ (c[14] ^ c[16])))) ^ (((c[17] ^ c[18]) ^ (c[19] ^ c[22])) ^ ((c[25] ^ c[26]) ^ (c[29] ^ (c[30] ^ c[31])))));
  crc_zero_run8[20]=((((c[2] ^ c[3]) ^ (c[5] ^ c[6])) ^ ((c[7] ^ c[8]) ^ (c[10] ^ c[14]))) ^ (((c[19] ^ c[20]) ^ (c[22] ^ c[23])) ^ ((c[24] ^ c[25]) ^ (c[26] ^ c[29]))));
  crc_zero_run8[21]=((((c[0] ^ c[1]) ^ (c[2] ^ (c[4] ^ c[5]))) ^ ((c[6] ^ c[7]) ^ (c[8] ^ (c[10] ^ c[12])))) ^ (((c[14] ^ c[17]) ^ (c[18] ^ (c[20] ^ c[21]))) ^ ((c[22] ^ c[23]) ^ (c[26] ^ (c[29] ^ c[31])))));
  crc_zero_run8[22]=(((c[0] ^ (c[6] ^ c[7])) ^ ((c[8] ^ c[10]) ^ (c[12] ^ c[13]))) ^ (((c[14] ^ c[17]) ^ (c[19] ^ c[21])) ^ ((c[23] ^ c[25]) ^ (c[29] ^ c[31]))));
  crc_zero_run8[23]=(((c[1] ^ (c[7] ^ c[8])) ^ ((c[9] ^ c[11]) ^ (c[13] ^ c[14]))) ^ ((c[15] ^ (c[18] ^ c[20])) ^ ((c[22] ^ c[24]) ^ (c[26] ^ c[30]))));
  crc_zero_run8[24]=(((c[1] ^ (c[3] ^ c[5])) ^ ((c[8] ^ c[11]) ^ (c[16] ^ c[17]))) ^ (((c[18] ^ c[19]) ^ (c[21] ^ c[22])) ^ ((c[23] ^ c[24]) ^ (c[29] ^ c[30]))));
  crc_zero_run8[25]=(((c[0] ^ (c[1] ^ c[3])) ^ ((c[4] ^ c[5]) ^ (c[6] ^ c[10]))) ^ (((c[11] ^ c[14]) ^ (c[15] ^ c[19])) ^ ((c[20] ^ c[23]) ^ (c[27] ^ c[29]))));
  crc_zero_run8[26]=((((c[0] ^ c[1]) ^ (c[2] ^ c[4])) ^ ((c[5] ^ c[6]) ^ (c[7] ^ c[11]))) ^ (((c[12] ^ c[15]) ^ (c[16] ^ c[20])) ^ ((c[21] ^ c[24]) ^ (c[28] ^ c[30]))));
  crc_zero_run8[27]=((((c[0] ^ c[6]) ^ (c[7] ^ c[8])) ^ ((c[9] ^ c[10]) ^ (c[11] ^ c[13]))) ^ (((c[14] ^ c[15]) ^ (c[16] ^ c[18])) ^ ((c[21] ^ c[24]) ^ (c[27] ^ c[30]))));
  crc_zero_run8[28]=(((c[2] ^ (c[3] ^ c[5])) ^ (c[7] ^ (c[8] ^ c[16]))) ^ ((c[18] ^ (c[19] ^ c[24])) ^ ((c[27] ^ c[28]) ^ (c[29] ^ c[30]))));
  crc_zero_run8[29]=(((c[0] ^ (c[3] ^ c[4])) ^ ((c[6] ^ c[8]) ^ (c[9] ^ c[17]))) ^ ((c[19] ^ (c[20] ^ c[25])) ^ ((c[28] ^ c[29]) ^ (c[30] ^ c[31]))));
  crc_zero_run8[30]=((((c[2] ^ c[3]) ^ (c[4] ^ c[7])) ^ ((c[11] ^ c[12]) ^ (c[14] ^ c[15]))) ^ (((c[17] ^ c[20]) ^ (c[21] ^ c[22])) ^ ((c[24] ^ c[25]) ^ (c[26] ^ c[27]))));
  crc_zero_run8[31]=((((c[0] ^ c[1]) ^ (c[2] ^ (c[4] ^ c[8]))) ^ ((c[9] ^ c[10]) ^ (c[11] ^ (c[13] ^ c[14])))) ^ (((c[16] ^ c[17]) ^ (c[21] ^ (c[23] ^ c[24]))) ^ ((c[26] ^ c[28]) ^ (c[29] ^ (c[30] ^ c[31])))));
 end
 endfunction
 function automatic [31:0] matrix_times;
  input [1023:0] matrix;input [31:0] value;
  integer m;begin matrix_times=0;for(m=0;m<32;m=m+1)if(value[m])matrix_times=matrix_times^matrix[m*32+:32];end
 endfunction
 function automatic [1023:0] shift_matrix;
  input integer bits_to_shift;reg [1023:0] power,result,squared;
  reg [31:0] column;integer c,remaining;begin
   for(c=0;c<32;c=c+1)begin column=32'b1<<c;result[c*32+:32]=column;power[c*32+:32]=(column>>1)^(column[0]?32'hEDB88320:32'b0);end
   remaining=bits_to_shift;
   while(remaining>0)begin
    if(remaining&1)begin for(c=0;c<32;c=c+1)squared[c*32+:32]=matrix_times(power,result[c*32+:32]);result=squared;end
    for(c=0;c<32;c=c+1)squared[c*32+:32]=matrix_times(power,power[c*32+:32]);
    power=squared;remaining=remaining>>1;
   end
   shift_matrix=result;
  end
 endfunction
 localparam [1023:0] ROW_SHIFT=shift_matrix(WIDTH*16);
 reg frame_active,collect_done,collect_bank,next_tx_bank,tx_bank;
 reg [1:0] bank_busy,bank_full;
 reg seal_valid,seal_bank;
 reg [SLOT_BITS-1:0] slot;
 reg [31:0] expected_tag,group_first,group_x,identity;
 reg [31:0] macro_y,macro_x_tag_step,macro_x_group_step;
 reg [CRC_ROW_BITS-1:0] group_y_offset;
 reg [5:0] macro_rows;
 reg [27:0] base,bank_address[0:1],tx_address;
 reg [1:0] tx_state;reg [2:0] tx_row;reg [BEAT_BITS-1:0] tx_beat;
 reg writes_complete,drain_pending;reg [5:0] drain;reg [TIMEOUT_BITS-1:0] watchdog;
 reg [31:0] crc_run,crc_fold_row;reg [1:0] crc_owned,crc_full;
 reg crc_collect_bank,crc_next_bank,crc_bank,crc_busy,crc_complete;
 reg [5:0] crc_rows[0:1];reg [CRC_ROW_BITS-1:0] crc_row;reg [4:0] crc_column;
 reg [31:0] crc_global,crc_mix,crc_macros_done;
 wire [31:0] fold_one=crc_mix^(crc_global[crc_column]?ROW_SHIFT[crc_column*32+:32]:32'b0);
 wire [31:0] fold_next=CRC_FOLD_BITS==2 ?
  (fold_one^(crc_global[{crc_column[4:1],1'b1}]?ROW_SHIFT[{crc_column[4:1],1'b1}*32+:32]:32'b0)):fold_one;
 wire fold_row_last=crc_column==32-CRC_FOLD_BITS;
 wire layout_ok=(ENABLE_BLACK_RUN8==0||ENABLE_BLACK_RUN8==1)&&(CRC_FOLD_BITS==1||CRC_FOLD_BITS==2)&&
  (MACRO_HEIGHT==8||MACRO_HEIGHT==16||MACRO_HEIGHT==32)&&
  (GROUP_WIDTH==16||GROUP_WIDTH==64||GROUP_WIDTH==128)&&
  WIDTH>=GROUP_WIDTH&&WIDTH<=8192&&WIDTH%GROUP_WIDTH==0&&
  HEIGHT>=8&&HEIGHT<=8192&&HEIGHT%8==0&&FRAME_PIXELS>0&&
  FRAME_PIXELS<=16777216&&TAG_W>=1&&TAG_W<=32&&FRAME_PIXELS<=(64'd1<<TAG_W)&&
  frame_base[6:0]==0&&({1'b0,frame_base}+FRAME_PIXELS/2)<=29'h10000000;
 assign frame_ready=!frame_active&&!failed&&tx_state==TX_IDLE&&bank_busy==0&&bank_full==0&&!seal_valid&&!drain_pending&&!crc_busy;
 wire frame_fire=frame_valid&&frame_ready;
 wire macro_first=group_x==0&&group_y_offset==0&&slot==0;
 assign in_ready=frame_active&&!failed&&!collect_done&&!drain_pending&&
  (slot!=0||!bank_busy[collect_bank])&&(!macro_first||!crc_owned[crc_collect_bank]);
 // Opt-in input transaction: scalar RGB565 pixel or one aligned run of 8 zeros.
 // A run is accepted in one clock and occupies eight logical scan positions.
 // The caller must prove the span is black for the frozen frame configuration.
 wire black_run8=ENABLE_BLACK_RUN8 && in_black_run8;
 wire [3:0] token_pixels=black_run8 ? 4'd8:4'd1;
 wire [31:0] token_last_tag=expected_tag+(black_run8 ? 32'd7:32'd0);
 wire pixel_fire=in_valid&&in_ready;
 wire bad_tag=pixel_fire&&(in_tag!=expected_tag ||
  (black_run8 && (slot[2:0]!=0 || in_rgb!=0 || accepted_pixels+8>FRAME_PIXELS)));
 wire good_pixel=pixel_fire&&!bad_tag;
 wire [15:0] pixel={in_rgb[23:19],in_rgb[15:10],in_rgb[7:3]};
 wire group_last=black_run8 ? slot==GROUP_PIXELS-8:slot==GROUP_PIXELS-1;
 wire [5:0] next_group_y={1'b0,group_y_offset}+6'd8;
 wire more_group_y=next_group_y<macro_rows;
 wire macro_last=group_last&&!more_group_y&&group_x==WIDTH-GROUP_WIDTH;
 wire [31:0] next_macro_y=macro_y+MACRO_HEIGHT;
 wire next_macro_is_tail=next_macro_y+MACRO_HEIGHT>HEIGHT;
 wire run_first=slot[2:0]==0,run_last=black_run8 || slot[2:0]==7;
 wire row_start=group_x==0&&slot<64;
 wire [5:0] collect_crc_row={1'b0,group_y_offset}+slot[5:3];
 wire [5:0] next_run_crc_row=group_last?(more_group_y?next_group_y:6'd0):
  ({1'b0,group_y_offset}+(slot[5:3]==7?6'd0:({3'b0,slot[5:3]}+6'd1)));
 wire [31:0] crc_read_q0,crc_read_q1;
 wire [31:0] collect_crc_q=crc_collect_bank?crc_read_q1:crc_read_q0;
 wire [31:0] fold_crc_q=crc_bank?crc_read_q1:crc_read_q0;
 wire [31:0] crc_run_seed=run_first?(row_start?32'b0:collect_crc_q):crc_run;
 wire [31:0] crc_run_next=black_run8 ? crc_zero_run8(crc_run_seed):video_crc32_pixel(crc_run_seed,pixel);
 wire collect_crc_read=good_pixel&&run_last&&!macro_last;
 wire fold_begin=!failed&&!bad_tag&&!crc_busy&&crc_full[crc_next_bank];
 wire fold_read_next=!failed&&!bad_tag&&crc_busy&&crc_column==0&&({1'b0,crc_row}+1'b1)<crc_rows[crc_bank];
 wire fold_crc_read=fold_begin||fold_read_next;
 wire fold_read_bank=fold_begin?crc_next_bank:crc_bank;
 wire [CRC_ROW_BITS-1:0] fold_read_row=fold_begin?{CRC_ROW_BITS{1'b0}}:crc_row+1'b1;
 wire accepted_aw=tx_state==TX_ADDRESS&&awready;
 wire transfer=(tx_state==TX_WRITE||accepted_aw)&&wready;
 wire bad_wlast=transfer&&wlast!=(tx_beat==ROW_BEATS-1);
 wire timed_out=tx_state==TX_WRITE&&(&watchdog)&&!wready;
 wire abandon=failed||bad_tag||bad_wlast||timed_out;
 assign awaddr=tx_address;assign awlen=ROW_BEATS-1;assign awvalid=tx_state==TX_ADDRESS;
 assign wstrb=32'hFFFFFFFF;
 always @(posedge clk)begin
  if(!rst_n)begin
   frame_active<=0;collect_done<=0;collect_bank<=0;next_tx_bank<=0;tx_bank<=0;
   bank_busy<=0;bank_full<=0;seal_valid<=0;seal_bank<=0;slot<=0;
   expected_tag<=0;group_first<=0;group_x<=0;identity<=0;base<=0;
   macro_y<=0;group_y_offset<=0;macro_rows<=FIRST_ROWS;
   macro_x_tag_step<=1-(FIRST_ROWS-1)*WIDTH;macro_x_group_step<=GROUP_WIDTH-(FIRST_ROWS-8)*WIDTH;
   tx_state<=TX_IDLE;tx_row<=0;tx_beat<=0;tx_address<=0;writes_complete<=0;
   drain_pending<=0;drain<=0;watchdog<=0;done<=0;failed<=0;fault<=0;
   accepted_pixels<=0;written_beats<=0;last_checksum<=0;completed_id<=0;
   crc_owned<=0;crc_full<=0;crc_collect_bank<=0;crc_next_bank<=0;
   crc_bank<=0;crc_busy<=0;crc_complete<=0;crc_row<=0;crc_column<=0;
   crc_global<=32'hFFFFFFFF;crc_mix<=0;crc_macros_done<=0;crc_run<=0;crc_fold_row<=0;crc_rows[0]<=0;crc_rows[1]<=0;
  end else begin
   done<=0;
   if(tx_state==TX_WRITE&&!wready)watchdog<=watchdog+1'b1;else watchdog<=0;
   if(frame_fire)begin
    if(!layout_ok||!frame_tiled)begin failed<=1;fault<=8'h08;end
    else begin
     frame_active<=1;collect_done<=0;collect_bank<=0;next_tx_bank<=0;tx_bank<=0;
     bank_busy<=0;bank_full<=0;seal_valid<=0;slot<=0;
     expected_tag<=0;group_first<=0;group_x<=0;macro_y<=0;group_y_offset<=0;macro_rows<=FIRST_ROWS;
     macro_x_tag_step<=1-(FIRST_ROWS-1)*WIDTH;macro_x_group_step<=GROUP_WIDTH-(FIRST_ROWS-8)*WIDTH;
     identity<=frame_id;base<=frame_base;tx_state<=TX_IDLE;tx_row<=0;tx_beat<=0;
     writes_complete<=0;drain_pending<=0;drain<=0;watchdog<=0;accepted_pixels<=0;written_beats<=0;
     crc_owned<=0;crc_full<=0;crc_collect_bank<=0;crc_next_bank<=0;crc_busy<=0;crc_complete<=0;crc_row<=0;crc_column<=0;
     crc_global<=32'hFFFFFFFF;crc_mix<=0;crc_macros_done<=0;crc_run<=0;crc_fold_row<=0;crc_rows[0]<=0;crc_rows[1]<=0;
    end
   end else begin
    seal_valid<=0;
    if(seal_valid&&!failed&&!bad_tag)bank_full[seal_bank]<=1;
    if(good_pixel)begin
     if(slot==0)begin bank_busy[collect_bank]<=1;bank_address[collect_bank]<=base+(group_first>>1);end
     accepted_pixels<=accepted_pixels+token_pixels;if(accepted_pixels+token_pixels==FRAME_PIXELS)collect_done<=1;
     slot<=slot+token_pixels;crc_run<=crc_run_next;
     if(!run_last)expected_tag<=expected_tag+1'b1;
     else if(slot[5:3]!=7)expected_tag<=token_last_tag+WIDTH-7;
     else if(group_last)begin
      if(more_group_y)expected_tag<=token_last_tag+WIDTH-GROUP_WIDTH+1;
      else if(group_x==WIDTH-GROUP_WIDTH)expected_tag<=token_last_tag+1'b1;
      else expected_tag<=token_last_tag+macro_x_tag_step;
     end else expected_tag<=token_last_tag-7*WIDTH+1;
     if(group_last)begin
      seal_valid<=1;seal_bank<=collect_bank;collect_bank<=!collect_bank;
      if(more_group_y)begin group_y_offset<=next_group_y[CRC_ROW_BITS-1:0];group_first<=group_first+8*WIDTH;end
      else begin
       group_y_offset<=0;
       if(group_x==WIDTH-GROUP_WIDTH)begin
        group_x<=0;group_first<=group_first+7*WIDTH+GROUP_WIDTH;
        if(accepted_pixels+token_pixels!=FRAME_PIXELS)begin
         macro_y<=next_macro_y;macro_rows<=next_macro_is_tail?TAIL_ROWS:MACRO_HEIGHT;
         macro_x_tag_step<=next_macro_is_tail?1-(TAIL_ROWS-1)*WIDTH:1-(MACRO_HEIGHT-1)*WIDTH;
         macro_x_group_step<=next_macro_is_tail?GROUP_WIDTH-(TAIL_ROWS-8)*WIDTH:GROUP_WIDTH-(MACRO_HEIGHT-8)*WIDTH;
        end
       end else begin group_x<=group_x+GROUP_WIDTH;group_first<=group_first+macro_x_group_step;end
      end
     end
     if(macro_first)begin crc_owned[crc_collect_bank]<=1;crc_rows[crc_collect_bank]<=macro_rows;end
     if(macro_last)begin crc_full[crc_collect_bank]<=1;crc_collect_bank<=!crc_collect_bank;end
    end
    case(tx_state)
     TX_IDLE:if(frame_active&&!abandon&&bank_full[next_tx_bank])begin tx_bank<=next_tx_bank;tx_row<=0;tx_beat<=0;tx_address<=bank_address[next_tx_bank];tx_state<=TX_ADDRESS;end
     TX_ADDRESS:if(awready)tx_state<=TX_WRITE;
     TX_WRITE:begin end
     default:begin failed<=1;fault<=8'h08;end
    endcase
    if(transfer)begin
     written_beats<=written_beats+1'b1;
     if(tx_beat==ROW_BEATS-1)begin
      tx_beat<=0;
      if(tx_row==7||abandon)begin tx_state<=TX_IDLE;bank_busy[tx_bank]<=0;bank_full[tx_bank]<=0;next_tx_bank<=!next_tx_bank;end
      else begin tx_row<=tx_row+1'b1;tx_address<=tx_address+WIDTH/2;tx_state<=TX_ADDRESS;end
     end else tx_beat<=tx_beat+1'b1;
     if(written_beats==FRAME_BEATS-1&&!abandon)begin if(accepted_pixels!=FRAME_PIXELS)begin failed<=1;fault<=8'h08;end else writes_complete<=1;end
    end
    if(!failed&&!bad_tag)begin
     if(fold_begin)begin crc_busy<=1;crc_bank<=crc_next_bank;crc_row<=0;crc_column<=0;crc_mix<=0;end
     else if(crc_busy)begin
      if(crc_column==0)crc_fold_row<=fold_crc_q;
      if(fold_row_last)begin
       crc_global<=fold_next^crc_fold_row;crc_mix<=0;crc_column<=0;
       if({1'b0,crc_row}==crc_rows[crc_bank]-1'b1)begin
        crc_busy<=0;crc_owned[crc_bank]<=0;crc_full[crc_bank]<=0;crc_next_bank<=!crc_next_bank;crc_macros_done<=crc_macros_done+1'b1;
        if(crc_macros_done==MACROS-1)crc_complete<=1;
       end else crc_row<=crc_row+1'b1;
      end else begin crc_mix<=fold_next;crc_column<=crc_column+CRC_FOLD_BITS;end
     end
    end
    if(frame_active&&writes_complete&&crc_complete&&!drain_pending&&!abandon)begin drain_pending<=1;drain<=0;end
    if(drain_pending&&!abandon)begin if(drain==31)begin last_checksum<=~crc_global;completed_id<=identity;done<=1;frame_active<=0;drain_pending<=0;end else drain<=drain+1'b1;end
    if(!failed)begin
     if(bad_wlast)begin failed<=1;fault<=8'h02;end
     else if(bad_tag)begin failed<=1;fault<=8'h32;end
     else if(timed_out)begin failed<=1;fault<=8'h01;end
    end
   end
  end
 end
 genvar crc_b;
 generate for(crc_b=0;crc_b<2;crc_b=crc_b+1)begin: row_crc_bank
  (* ram_style="block" *) reg [31:0] partial[0:MACRO_HEIGHT-1];reg [31:0] read_q;
  wire collect_read=collect_crc_read&&crc_collect_bank==crc_b;
  wire folding_read=fold_crc_read&&fold_read_bank==crc_b;
  wire read_enable=rst_n&&(collect_read||folding_read);
  wire [CRC_ROW_BITS-1:0] read_address=folding_read?fold_read_row:next_run_crc_row[CRC_ROW_BITS-1:0];
  always @(posedge clk)if(rst_n&&good_pixel&&run_last&&crc_collect_bank==crc_b)partial[collect_crc_row[CRC_ROW_BITS-1:0]]<=crc_run_next;
  always @(posedge clk)if(read_enable)read_q<=partial[read_address];
  if(crc_b==0)assign crc_read_q0=read_q;else assign crc_read_q1=read_q;
 end endgenerate
    // Canonical full-word16-bit write / synchronous read lane RAM organization.
    // No vendor primitive or inference claim. Payload =256*GROUP_WIDTH bits
    // for BOTH banks:512B/2KiB/4KiB at group16/64/128. Physical RAM cost awaits Map.
    reg write_pending;
    reg [WORD_ADDR_BITS-1:0] write_word;
    reg [15:0] write_mask;
    reg [15:0] write_pixel;
    // The fields do not overlap: row selects B words; tile-pair selects
    // the beat within that row. Constant shifts/OR avoid an address adder.
    wire [WORD_ADDR_BITS-2:0] collect_row_extended={{(WORD_ADDR_BITS-4){1'b0}},slot[5:3]};
    wire [WORD_ADDR_BITS-2:0] collect_row_word=(collect_row_extended<<ROW_BEAT_LOG) | (slot>>7);
    wire [WORD_ADDR_BITS-1:0] command_word={collect_bank,collect_row_word};
    wire [3:0] command_lane={slot[6],slot[2:0]};
    always @(posedge clk)begin
        if(!rst_n || failed)write_pending<=0;
        else begin
            write_pending<=good_pixel;
            if(good_pixel)begin
                write_word<=command_word;
                write_mask<=black_run8 ? (slot[6] ? 16'hFF00:16'h00FF):(16'b1<<command_lane);
                write_pixel<=black_run8 ? 16'b0:pixel;
            end
        end
    end
    wire read_first=tx_state==TX_IDLE && frame_active && !abandon && bank_full[next_tx_bank];
    // Never gate the rest of an ISSUED burst with failed. Only the next
    // unissued row is suppressed. A stalled W does not overwrite read_pixel.
    wire row_last=tx_beat==ROW_BEATS-1;
    wire read_next=transfer && (!row_last || (tx_row!=7 && !abandon));
    wire read_enable=rst_n && (read_first || read_next);
    wire [2:0] next_row=row_last ? tx_row+3'd1:tx_row;
    wire [BEAT_BITS-1:0] next_beat=row_last ? {BEAT_BITS{1'b0}}:tx_beat+1'b1;
    wire [WORD_ADDR_BITS-2:0] next_row_extended={{(WORD_ADDR_BITS-4){1'b0}},next_row};
    wire [WORD_ADDR_BITS-2:0] next_row_word=(next_row_extended<<ROW_BEAT_LOG) | next_beat;
    wire [WORD_ADDR_BITS-1:0] read_word=read_first ?
        {next_tx_bank,{(WORD_ADDR_BITS-1){1'b0}}}:{tx_bank,next_row_word};
    genvar lane;
    generate for(lane=0;lane<16;lane=lane+1)begin: pixel_lane
        reg [15:0] pixels[0:16*ROW_BEATS-1];
        reg [15:0] read_pixel;
        always @(posedge clk)if(write_pending && write_mask[lane])
            pixels[write_word]<=write_pixel;
        always @(posedge clk)if(read_enable)read_pixel<=pixels[read_word];
        assign wdata[lane*16+:16]=read_pixel;
    end endgenerate
endmodule
