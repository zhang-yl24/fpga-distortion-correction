`timescale 1ps/1ps
module tb_dma_descriptor2;
 localparam W=16,H=16,N=256,STRIDE=1048576;
 reg clk=0,pclk=0,rst_n=0,enable=0;always #4000 clk=~clk;
 integer pixel_phase=0,pixel_delay;
 initial forever begin pixel_phase=pixel_phase+2000000;pixel_delay=pixel_phase/297;pixel_phase=pixel_phase%297;#(pixel_delay)pclk=~pclk;end
 reg vs=0,de=0;reg [23:0] rgb=0;reg [1:0] source_writable=3;
 reg source_ready=0,source_released=0,released_bank=0;
 wire source_valid,source_bank,failed;wire [31:0] source_id,source_crc,source_pixels;
 wire [1:0] capture_reserved;wire [27:0] awaddr;wire [3:0] awlen;wire awvalid;
 wire [255:0] wdata;wire [31:0] wstrb;reg awready=0,wready=0,wlast=0;
 wire write_active;wire [7:0] fault,last_drop_fault;wire [31:0] accepted,dropped,overflow,no_free;
 hdmi1080_input_dma #(.WIDTH(W),.HEIGHT(H),.BANK_STRIDE(STRIDE)) dut(
  .pix_clk(pclk),.sys_clk(clk),.rst_n(rst_n),.enable(enable),.pix_vsync_active(vs),.pix_de(de),.pix_rgb(rgb),
  .source_writable(source_writable),.source_released(source_released),.released_bank(released_bank),
  .source_valid(source_valid),.source_ready(source_ready),.source_bank(source_bank),.source_id(source_id),.source_crc(source_crc),.source_pixels(source_pixels),
  .capture_reserved(capture_reserved),.awaddr(awaddr),.awlen(awlen),.awvalid(awvalid),.awready(awready),
  .wdata(wdata),.wstrb(wstrb),.wready(wready),.wlast(wlast),.write_active(write_active),.failed(failed),.fault(fault),
  .accepted_frames(accepted),.dropped_frames(dropped),.overflow_frames(overflow),.no_free_frames(no_free),.last_drop_fault(last_drop_fault));
 reg [15:0] vectors[0:6*N-1];reg [31:0] crcs[0:5];
 integer phase=0,ticks=0,wleft=0,beat=0,current_seed=0,aw_total=0,beats_total=0,desc_total=0;
 integer logf,writesf,descf,awf,hold_cycles=0,full_cycles=0,prefetch_witness=0,simultaneous=0,reset_full=0,reset_reserved=0;
 reg held=0;reg [96:0] held_tuple;
 function [23:0] expand565(input [15:0] p);begin expand565={p[15:11],p[15:13],p[10:5],p[10:9],p[4:0],p[4:2]};end endfunction
 task automatic event_log(input [8*24-1:0] name);begin
  $fdisplay(logf,"%0s,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d",name,phase,$time,source_valid,dut.source_tail_valid,dut.active,source_id,dut.active_id,capture_reserved,dut.descriptor_credit,accepted);$fflush(logf);
 end endtask
 always @(negedge clk)begin
  ticks=ticks+1;awready=rst_n&&wleft==0&&ticks%3!=0;
  wready=rst_n&&wleft>0&&ticks%4!=0;wlast=wleft==1;
 end
 integer j,bank,occupancy;
 always @(posedge clk)begin
  if(!rst_n)begin wleft<=0;beat<=0;held<=0;end
  else begin
   if(failed||dropped||overflow||last_drop_fault||no_free)$fatal(1,"normal descriptor unit unexpected DMAfault/drop");
   occupancy=(source_valid?1:0)+(dut.source_tail_valid?1:0)+(dut.active?1:0);
   if(occupancy>2||(!source_valid&&dut.source_tail_valid))$fatal(1,"descriptor credit/contiguity overflow");
   if(source_valid&&dut.active&&source_bank==dut.active_bank)$fatal(1,"active capture reused pending source bank");
   if(source_valid&&dut.source_tail_valid&&source_bank==dut.source_tail_bank)$fatal(1,"two pending tuples alias bank");
   if(held&&{source_bank,source_id,source_crc,source_pixels}!==held_tuple)$fatal(1,"stalled whole source tuple overwritten");
   held<=source_valid&&!source_ready;held_tuple<={source_bank,source_id,source_crc,source_pixels};
   if(source_valid&&!source_ready)hold_cycles=hold_cycles+1;
   if(dut.source_tail_valid)begin
    full_cycles=full_cycles+1;
    if(dut.descriptor_credit||dut.grant_valid||dut.active)$fatal(1,"full descriptor queue allowed reservation");
   end
   if(dut.cap_done_ready&&dut.cap_done_valid&&source_valid&&source_ready)begin
    simultaneous=simultaneous+1;event_log("POP_PUSH");
   end
   if(source_valid&&source_ready)begin
    desc_total=desc_total+1;
    $fdisplay(descf,"%0d,%0d,%0d,%08h,%0d,%0d",phase,source_id,source_bank,source_crc,source_pixels,$time);$fflush(descf);
   end
   if(awvalid&&awready)begin
    if(awlen!=15||awaddr%STRIDE!=0)$fatal(1,"unit source AW layout");
    aw_total=aw_total+1;current_seed=aw_total;bank=awaddr/STRIDE;
    if(bank!=((current_seed==2||current_seed==4)?1:0))$fatal(1,"unit source bank sequence");
    $fdisplay(awf,"%0d,%0d,%0d,%0d,%0d,%0d",phase,current_seed,awaddr,awlen,bank,$time);$fflush(awf);
    wleft<=16;beat<=0;
   end
   if(wleft>0&&wready)begin
    if(wlast!=(beat==15)||wstrb!==32'hffffffff)$fatal(1,"unit DDR last/strobe");
    for(j=0;j<16;j=j+1)if(wdata[j*16+:16]!==vectors[(current_seed-1)*N+beat*16+j])$fatal(1,"unit DDR independent pixel mismatch");
    $fdisplay(writesf,"%0d,%0d,%0d,%064h,%0d",phase,current_seed,beat,wdata,$time);$fflush(writesf);
    beats_total=beats_total+1;beat<=beat+1;wleft<=wleft-1;
   end
  end
 end
 task automatic send_frame(input integer seed);
  integer x,y;begin
   @(negedge pclk);
   for(y=0;y<24;y=y+1)for(x=0;x<24;x=x+1)begin
    vs=y<1;de=y>=2&&y<18&&x>=4&&x<20;
    rgb=de?expand565(vectors[(seed-1)*N+(y-2)*W+x-4]):0;
    @(negedge pclk);
   end
   vs=1;de=0;rgb=0;@(posedge pclk);@(negedge pclk);
  end
 endtask
 task automatic check_head(input integer ident,input integer seed,input integer b);begin
  if(!source_valid||source_id!=ident||source_bank!=b||source_pixels!=N||source_crc!==crcs[seed-1])$fatal(1,"unit queued descriptor tuple/CRC");
 end endtask
 task automatic wait_prefetch(input integer ident);begin
  wait(dut.active&&dut.active_id==ident&&dut.capture.pending_grant&&dut.capture.pending_id==ident);
  if(!source_valid||source_ready||dut.source_tail_valid)$fatal(1,"prefetch did not coexist with one stalled head");
  prefetch_witness=prefetch_witness+1;event_log("PREFETCH_WITH_HEAD");
 end endtask
 task automatic pop_head(input integer ident,input integer seed,input integer b);begin
  check_head(ident,seed,b);@(negedge clk);source_ready=1;
  @(posedge clk);#1;@(negedge clk);source_ready=0;
 end endtask
 task automatic release_bank(input integer b);begin
  @(negedge clk);released_bank=b;source_released=1;
  @(negedge clk);source_released=0;
 end endtask
 task automatic common_reset(input integer next_phase);begin
  @(negedge clk);rst_n=0;enable=0;source_ready=0;source_released=0;vs=0;de=0;rgb=0;
  phase=next_phase;repeat(12)@(negedge clk);
  if(source_valid||dut.source_tail_valid||dut.active||capture_reserved!=0||dut.next_id!=1)$fatal(1,"common reset left descriptor/reservation state");
  event_log("RESET_CLEARED");rst_n=1;enable=1;repeat(12)@(negedge clk);
 end endtask
 initial begin
  $readmemh("unit_source.mem",vectors);$readmemh("unit_crc.mem",crcs);
  logf=$fopen("queue_events.csv","w");writesf=$fopen("queue_writes.csv","w");descf=$fopen("queue_descriptors.csv","w");awf=$fopen("queue_aw.csv","w");
  $fdisplay(logf,"event,phase,time_ps,head,tail,reserved,id,active_id,owned,credit,accepted");
  $fdisplay(writesf,"phase,seed,beat,data,time_ps");$fdisplay(descf,"phase,id,bank,crc,pixels,time_ps");$fdisplay(awf,"phase,seed,address,len,bank,time_ps");
  common_reset(0);wait(dut.capture.pending_grant&&dut.capture.pending_id==1);
  send_frame(1);wait(source_valid);check_head(1,1,0);wait_prefetch(2);
  send_frame(2);wait(dut.source_tail_valid);check_head(1,1,0);
  repeat(32)@(negedge clk);if(!dut.source_tail_valid)$fatal(1,"full queue not held");
  reset_full=reset_full+1;event_log("RESET_FULL");
  common_reset(1);wait(dut.capture.pending_grant&&dut.capture.pending_id==1);
  send_frame(3);wait(source_valid);check_head(1,3,0);wait_prefetch(2);
  send_frame(4);wait(dut.source_tail_valid);repeat(8)@(negedge clk);
  pop_head(1,3,0);check_head(2,4,1);release_bank(0);wait_prefetch(3);
  send_frame(5);wait(dut.cap_done_valid&&dut.cap_done_ready);
  @(negedge clk);source_ready=1;
  @(posedge clk);#1;check_head(3,5,0);
  if(dut.source_tail_valid||accepted!=2||simultaneous!=1)$fatal(1,"atomic one-entry pop+push failed");
  @(negedge clk);source_ready=0;release_bank(1);wait_prefetch(4);
  reset_reserved=reset_reserved+1;event_log("RESET_RESERVED");
  common_reset(2);wait(dut.capture.pending_grant&&dut.capture.pending_id==1);
  send_frame(6);wait(source_valid);check_head(1,6,0);
  @(negedge clk);enable=0;source_ready=1;@(posedge clk);#1;
  @(negedge clk);source_ready=0;release_bank(0);repeat(12)@(negedge clk);
  if(source_valid||dut.source_tail_valid||dut.active||capture_reserved!=0||wleft!=0||aw_total!=6||beats_total!=96||desc_total!=3||simultaneous!=1||reset_full!=1||reset_reserved!=1||prefetch_witness<4||full_cycles<32||hold_cycles<32)$fatal(1,"descriptor unit final coverage/drain");
  event_log("TERMINAL");$fflush();$fclose(logf);$fclose(writesf);$fclose(descf);$fclose(awf);
  $display("PASS DMA_DESCRIPTOR2 dataframes=6 descriptors=3 beats=96 poppush=1 resetfull=1 resetreserved=1");$fflush();$finish;
 end
 initial begin #200000000;$fatal(1,"descriptor unit watchdog200us");end
endmodule
