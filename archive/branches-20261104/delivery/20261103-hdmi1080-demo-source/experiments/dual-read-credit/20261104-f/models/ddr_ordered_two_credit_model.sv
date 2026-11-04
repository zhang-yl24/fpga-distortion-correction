`timescale 1ns/1ps
// TEST ONLY. Explicitly different contract from ddr_shared_pressure_model.
// Two accepted ordered ID0 read commands; one pending write command. Per-AR
// latency timers run concurrently, including during unrelated writes. One shared
// payload bus, whole-burst R/W round robin, reset-anchored absolute blackouts.
// This synthetic model does not establish a Pango IP outstanding/order contract.
module ddr_ordered_two_credit_model #(
 parameter integer AR_DELAY=0,AW_DELAY=0,R_LATENCY=32,W_LATENCY=0,R_GAP=0,W_GAP=0,
 parameter integer TURN_CYCLES=0,REF_PERIOD=0,REF_CYCLES=0,REF_PHASE=0,
 parameter integer STOP_PERIOD=0,STOP_CYCLES=0,STOP_PHASE=0
)(
 input wire clk,rst_n,input wire [27:0] araddr,awaddr,input wire [3:0] arlen,awlen,
 input wire arvalid,awvalid,output wire arready,awready,
 output wire [255:0] rdata,output wire rvalid,rlast,output wire [3:0] rid,
 input wire [255:0] wdata,input wire [31:0] wstrb,output wire wready,wlast,
 output wire [27:0] mem_raddr,mem_waddr,input wire [255:0] mem_rdata,
 output wire mem_we,output wire [255:0] mem_wdata,output wire [31:0] mem_wstrb,
 output wire refresh_active,stop_active,output reg [63:0] tick,
 output reg [63:0] read_commands,write_commands,read_beats,write_beats,
 output reg [63:0] refresh_cycles,stop_cycles,turn_wait_cycles
);
 localparam IDLE=0,READ=1,WRITE=2;
 reg [1:0] state,qcount;reg rp,wp;
 reg [27:0] raddress[0:1];reg [4:0] rleft[0:1];reg [63:0] rdue[0:1];
 reg wpending;reg [27:0] waddress;reg [4:0] wleft;reg [63:0] wdue;
 integer ar_age,aw_age;
 reg last_was_write,have_last;reg [63:0] last_payload;
 reg held_ar,held_aw;reg [31:0] saved_ar,saved_aw;
 reg [1:0] peak_reads;reg [63:0] latency_overlap_commands;
 function automatic in_window(input [63:0] t,input integer period,count,phase);
 reg [63:0] position;begin
  if(period==0||count==0)in_window=0;
  else begin position=(t+period-(phase%period))%period;in_window=position<count;end
 end endfunction
 assign refresh_active=rst_n&&in_window(tick,REF_PERIOD,REF_CYCLES,REF_PHASE);
 assign stop_active=rst_n&&in_window(tick,STOP_PERIOD,STOP_CYCLES,STOP_PHASE);
 wire blocked=refresh_active||stop_active;
 wire eligible_r=qcount!=0&&tick>=rdue[rp];
 wire eligible_w=wpending&&tick>=wdue;
 wire choose_r=eligible_r&&(!eligible_w||last_was_write);
 wire choose_w=eligible_w&&!choose_r;
 wire turn_ok=!have_last||((choose_r&&!last_was_write)||(choose_w&&last_was_write))||tick>=last_payload+1+TURN_CYCLES;
 wire serve_r=state==READ||(state==IDLE&&choose_r&&turn_ok);
 wire serve_w=state==WRITE||(state==IDLE&&choose_w&&turn_ok);
 assign rvalid=rst_n&&serve_r&&eligible_r&&!blocked;
 assign wready=rst_n&&serve_w&&eligible_w&&!blocked;
 assign rlast=rleft[rp]==1;assign wlast=wleft==1;assign rid=0;
 wire pop=rvalid&&rlast;
 assign arready=rst_n&&!blocked&&(qcount<2||pop)&&arvalid&&ar_age>=AR_DELAY;
 assign awready=rst_n&&!blocked&&!wpending&&awvalid&&aw_age>=AW_DELAY;
 wire push=arvalid&&arready;
 assign mem_raddr=raddress[rp];assign mem_waddr=waddress;assign rdata=mem_rdata;
 assign mem_we=wready;assign mem_wdata=wdata;assign mem_wstrb=wstrb;
 always @(posedge clk)begin
  if(!rst_n)begin
   state<=IDLE;qcount<=0;rp<=0;wp<=0;wpending<=0;waddress<=0;wleft<=0;wdue<=0;
   raddress[0]<=0;raddress[1]<=0;rleft[0]<=0;rleft[1]<=0;rdue[0]<=0;rdue[1]<=0;
   ar_age<=0;aw_age<=0;last_was_write<=1;have_last<=0;last_payload<=0;
   held_ar<=0;held_aw<=0;saved_ar<=0;saved_aw<=0;
   tick<=0;read_commands<=0;write_commands<=0;read_beats<=0;write_beats<=0;
   refresh_cycles<=0;stop_cycles<=0;turn_wait_cycles<=0;peak_reads<=0;latency_overlap_commands<=0;
  end else begin
   tick<=tick+1;
   if(held_ar&&(!arvalid||{arlen,araddr}!==saved_ar))$fatal(1,"queued model AR changed while stalled");
   if(held_aw&&(!awvalid||{awlen,awaddr}!==saved_aw))$fatal(1,"queued model AW changed while stalled");
   if(rvalid&&wready)$fatal(1,"queued model simultaneous read/write payload");
   if(qcount>2)$fatal(1,"queued model read capacity overflow");
   held_ar<=arvalid&&!arready;saved_ar<={arlen,araddr};held_aw<=awvalid&&!awready;saved_aw<={awlen,awaddr};
   if(!arvalid||arready)ar_age<=0;else if(ar_age<AR_DELAY)ar_age<=ar_age+1;
   if(!awvalid||awready)aw_age<=0;else if(aw_age<AW_DELAY)aw_age<=aw_age+1;
   if(refresh_active)refresh_cycles<=refresh_cycles+1;
   if(stop_active)stop_cycles<=stop_cycles+1;
   if(state==IDLE&&!blocked&&(choose_r||choose_w)&&!turn_ok)turn_wait_cycles<=turn_wait_cycles+1;
   if(push)begin
    if(araddr[2:0]!=0)$fatal(1,"queued model unaligned AR");
    raddress[wp]<=araddr;rleft[wp]<={1'b0,arlen}+1'b1;rdue[wp]<=tick+R_LATENCY+1;wp<=!wp;
    read_commands<=read_commands+1;
    if(qcount!=0&&tick<rdue[rp])latency_overlap_commands<=latency_overlap_commands+1;
   end
   if(pop)rp<=!rp;
   case({push,pop})
    2'b10:qcount<=qcount+1'b1;
    2'b01:qcount<=qcount-1'b1;
    default:qcount<=qcount;
   endcase
   if(qcount>peak_reads)peak_reads<=qcount;
   if(awvalid&&awready)begin
    if(awaddr[2:0]!=0)$fatal(1,"queued model unaligned AW");
    wpending<=1;waddress<=awaddr;wleft<={1'b0,awlen}+1'b1;wdue<=tick+W_LATENCY+1;write_commands<=write_commands+1;
   end
   if(rvalid)begin
    read_beats<=read_beats+1;last_payload<=tick;last_was_write<=0;have_last<=1;
    if(rlast)state<=IDLE;
    else begin raddress[rp]<=raddress[rp]+8;rleft[rp]<=rleft[rp]-1'b1;rdue[rp]<=tick+R_GAP+1;state<=READ;end
   end
   if(wready)begin
    write_beats<=write_beats+1;last_payload<=tick;last_was_write<=1;have_last<=1;
    if(wlast)begin state<=IDLE;wpending<=0;end
    else begin waddress<=waddress+8;wleft<=wleft-1'b1;wdue<=tick+W_GAP+1;state<=WRITE;end
   end
  end
 end
 initial begin
  if(AR_DELAY<0||AW_DELAY<0||R_LATENCY<0||W_LATENCY<0||R_GAP<0||W_GAP<0||TURN_CYCLES<0||
   REF_PERIOD<0||REF_CYCLES<0||REF_PHASE<0||STOP_PERIOD<0||STOP_CYCLES<0||STOP_PHASE<0||
   (REF_CYCLES!=0&&(REF_PERIOD==0||REF_CYCLES>=REF_PERIOD))||
   (STOP_CYCLES!=0&&(STOP_PERIOD==0||STOP_CYCLES>=STOP_PERIOD)))$fatal(1,"queued model invalid parameters");
 end
endmodule
