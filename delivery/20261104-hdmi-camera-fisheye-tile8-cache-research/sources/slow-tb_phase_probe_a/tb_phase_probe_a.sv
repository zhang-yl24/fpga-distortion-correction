`timescale 1ps/1ps
// True frozen input DMA/capture/FIFO + bank RTL. Engine and display lease are
// explicit duration stubs. Time periods are 1/1000 of the physical intervals.
module tb_phase_probe_a;
  localparam W=16,H=16,STRIDE=1048576,OP=4167,ENDC=20*OP;
  reg clk=0,pclk=0,rst_n=0; always #4000 clk=~clk; always #3367 pclk=~pclk;
  integer cy=0,pc=0,proc,phase,fd,fs;
  reg vs=0,de=0; reg [23:0] rgb=24'h336699;
  wire src_valid,src_ready,src_bank,source_release,released_bank;
  wire [31:0] src_id,src_crc,src_pixels,accepted,dropped,overflows,nofree;
  wire [1:0] writable,reserved;
  wire dma_failed,bank_failed; wire [7:0] dma_fault,bank_fault;
  wire [27:0] awaddr;wire [3:0] awlen;wire awvalid;wire [255:0] wdata;wire [31:0] wstrb;
  reg wb=0;reg [3:0] beat=0;
  wire awready=awvalid&&!wb;wire wready=wb;wire wlast=wb&&beat==15;
  wire enable=1'b1;
  wire [1:0] capture_writable=cy<ENDC ? writable:2'b00;
  hdmi1080_input_dma #(.WIDTH(W),.HEIGHT(H),.BANK_STRIDE(STRIDE)) dma(
    .pix_clk(pclk),.sys_clk(clk),.rst_n(rst_n),.enable(enable),.pix_vsync_active(vs),.pix_de(de),.pix_rgb(rgb),
    .source_writable(capture_writable),.source_released(source_release),.released_bank(released_bank),
    .source_valid(src_valid),.source_ready(src_ready),.source_bank(src_bank),.source_id(src_id),
    .source_crc(src_crc),.source_pixels(src_pixels),.capture_reserved(reserved),
    .awaddr(awaddr),.awlen(awlen),.awvalid(awvalid),.awready(awready),.wdata(wdata),.wstrb(wstrb),
    .wready(wready),.wlast(wlast),.write_active(),.failed(dma_failed),.fault(dma_fault),
    .accepted_frames(accepted),.dropped_frames(dropped),.overflow_frames(overflows),.no_free_frames(nofree),.last_drop_fault());
  reg req=0,ddone=0,donebank=0;wire reqready,gv;wire [27:0] dbase;wire [31:0] did,dcrc;
  wire processing,pending,display_active,write_bank,front_bank;wire [31:0] completed,lastcycles;
  hdmi_camera_fisheye_bank #(.WIDTH(W),.HEIGHT(H),.BANK_STRIDE(STRIDE)) bank(
    .clk(clk),.rst_n(rst_n),.source_valid(src_valid),.source_ready(src_ready),.source_bank(src_bank),.source_id(src_id),
    .source_writable(writable),.source_released(source_release),.released_bank(released_bank),
    .display_request_valid(req),.display_request_ready(reqready),.display_grant_valid(gv),.display_grant_ready(1'b1),
    .display_base(dbase),.display_crc(dcrc),.display_id(did),.display_done_valid(ddone),.display_done_bank(donebank),
    .cfg_corrected(1'b1),.araddr(),.arlen(),.arvalid(),.arready(1'b1),.rdata(256'b0),.rvalid(1'b0),.rlast(1'b0),.rid(4'b0),
    .awaddr(),.awlen(),.awvalid(),.awready(1'b1),.wdata(),.wstrb(),.wready(1'b0),.wlast(1'b0),
    .processing(processing),.pending(pending),.display_active(display_active),.write_bank(write_bank),.front_bank(front_bank),
    .completed_frames(completed),.last_cycles(lastcycles),.hits(),.misses(),.queries(),.failed(bank_failed),.fault(bank_fault));
  integer deadline=0;reg lease=0;reg [31:0] lease_id=0,last_id=0;
  integer refresh=0,unique_count=0,repeats=0,blank=0,process_count=0,accept_count=0;
  reg old_sv=0,old_pending=0,old_start=0;
  integer live_id,stamp_accept,stamp_offer,stamp_grant;
  integer pending_wait=0,offer_wait=0,processing_cycles=0;
  always @(posedge pclk)begin
    if(!rst_n)begin pc<=0;vs<=0;de<=0;end
    else begin
      pc<=pc==2474?0:pc+1;
      vs<=pc<16;
      de<=pc>=80 && ((pc-80)/144)<H && ((pc-80)%144)<W;
    end
  end
  task eventlog(input [191:0] kind,input integer id,input integer b);
    begin $fdisplay(fd,"%0d,%0s,%0d,%0d,%0d,%0d,%0d,%0d",cy,kind,id,b,processing,pending,display_active,src_valid);end
  endtask
  always @(posedge clk)begin
    if(!rst_n)begin cy<=0;wb<=0;beat<=0;end
    else begin
      cy<=cy+1;req<=0;ddone<=0;
      if(awvalid&&awready)begin wb<=1;beat<=0;end
      if(wready)begin if(beat==15)begin wb<=0;beat<=0;end else beat<=beat+1;end
      if(dma_failed||bank_failed)$fatal(1,"DUT fault dma=%h bank=%h",dma_fault,bank_fault);
      if(dma.grant_valid&&dma.grant_ready)eventlog("capture_grant",dma.next_id,dma.grant_bank);
      if(src_valid&&!old_sv)eventlog("source_offer",src_id,src_bank);
      if(src_valid&&src_ready)begin eventlog("source_accept",src_id,src_bank);if(cy>=4*OP&&cy<ENDC)accept_count<=accept_count+1;end
      if(bank.start)eventlog("engine_start",bank.accepted_id,bank.active_source);
      if(bank.engine_done)begin eventlog("engine_done",bank.accepted_id,bank.active_source);if(cy>=4*OP&&cy<ENDC)process_count<=process_count+1;end
      if(pending&&!old_pending)eventlog("pending_set",bank.pending_id,write_bank);
      if(!pending&&old_pending)eventlog("pending_clear",bank.front_id,front_bank);
      old_sv<=src_valid;old_pending<=pending;
      if(cy>=4*OP&&cy<ENDC)begin
        if(pending)pending_wait<=pending_wait+1;
        if(src_valid&&!src_ready)offer_wait<=offer_wait+1;
        if(processing)processing_cycles<=processing_cycles+1;
      end
      if(cy>=phase && ((cy-phase)%OP)==0 && cy<ENDC+5*OP)begin
        eventlog("scan_boundary",0,0);
        if(cy>=4*OP&&cy<ENDC)refresh<=refresh+1;
        if(reqready)req<=1;
        else if(cy>=4*OP&&cy<ENDC)blank<=blank+1;
      end
      if(gv)begin
        if(lease)$fatal(1,"overlapping display lease");
        eventlog("display_grant",did,front_bank);
        lease<=1;lease_id<=did;donebank<=front_bank;deadline<=cy+4000;
      end
      if(lease&&cy==deadline)begin
        eventlog("display_done",lease_id,donebank);ddone<=1;lease<=0;
        if(cy>=4*OP&&cy<ENDC)begin
          if(lease_id>last_id)unique_count<=unique_count+1;else if(lease_id==last_id)repeats<=repeats+1;else $fatal(1,"nonmonotonic ID");
        end
        last_id<=lease_id;
      end
      if(cy==ENDC+6*OP)begin
        if(processing||pending||src_valid||dma.active||wb||lease)$fatal(1,"not drained");
        if(overflows!=0||dropped!=0)$fatal(1,"unexpected capture integrity failure drop=%0d overflow=%0d",dropped,overflows);
        if(lastcycles!=proc+1)$fatal(1,"stub duration mismatch requested=%0d actual=%0d",proc,lastcycles);
        $fdisplay(fs,"{\"passed\":true,\"process_stub_cycles\":%0d,\"phase\":%0d,\"window_cycles\":%0d,\"output_period\":%0d,\"refreshes\":%0d,\"unique\":%0d,\"repeats\":%0d,\"blank\":%0d,\"accepted\":%0d,\"processed\":%0d,\"pending_cycles\":%0d,\"offer_wait_cycles\":%0d,\"processing_cycles\":%0d,\"no_grant\":%0d,\"last_measured_process_cycles\":%0d,\"drained\":true}",proc,phase,16*OP,OP,refresh,unique_count,repeats,blank,accept_count,process_count,pending_wait,offer_wait,processing_cycles,nofree,lastcycles);
        $display("PASS PHASE PROBE proc=%0d phase=%0d unique=%0d repeat=%0d refresh=%0d",proc,phase,unique_count,repeats,refresh);$fclose(fd);$fclose(fs);$finish;
      end
    end
  end
  initial begin
    if(!$value$plusargs("PROC=%d",proc))proc=4433;
    if(!$value$plusargs("PHASE=%d",phase))phase=0;
    fd=$fopen("events.csv","w");fs=$fopen("summary.json","w");
    $fdisplay(fd,"cycle,event,id,bank,processing,pending,display_active,source_valid");
    #1000 bank.engine.duration=proc;
    #159000 rst_n=1;
  end
  initial begin #(64'd100000000000) $fatal(1,"bench timeout");end
endmodule

module hdmi_camera_fisheye_engine_tile8 #(parameter WIDTH=1920,HEIGHT=1080,TIMEOUT_BITS=26)(
 input clk,rst_n,input frame_valid,output frame_ready,input cfg_corrected,
 input[27:0]source_base,output_base,input[31:0]frame_id,
 output[27:0]araddr,output[3:0]arlen,output arvalid,input arready,input[255:0]rdata,input rvalid,rlast,input[3:0]rid,
 output[27:0]awaddr,output[3:0]awlen,output awvalid,input awready,output[255:0]wdata,output[31:0]wstrb,input wready,wlast,
 output reg done,output failed,output[7:0]fault,output reg[27:0]completed_base,output reg[31:0]completed_id,completed_crc,
 output[31:0]hits,misses,completed_queries);
 integer duration=4433,count;reg busy=0;
 assign frame_ready=!busy;assign failed=0;assign fault=0;assign araddr=0;assign arlen=0;assign arvalid=0;
 assign awaddr=0;assign awlen=0;assign awvalid=0;assign wdata=0;assign wstrb=0;assign hits=0;assign misses=0;assign completed_queries=0;
 always @(posedge clk)begin
   if(!rst_n)begin busy<=0;done<=0;count<=0;completed_base<=0;completed_id<=0;completed_crc<=0;end
   else begin
     done<=0;
     if(frame_valid&&frame_ready)begin busy<=1;count<=0;completed_base<=output_base;completed_id<=frame_id;completed_crc<=0;end
     else if(busy)begin if(count==duration-1)begin done<=1;busy<=0;end else count<=count+1;end
   end
 end
endmodule
