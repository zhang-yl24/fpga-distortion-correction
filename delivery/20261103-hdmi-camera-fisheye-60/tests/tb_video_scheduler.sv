`timescale 1ns/1ps
module tb_scheduler;
`ifdef THREE
 localparam BANKS=3;
`else
 localparam BANKS=2;
`endif
 localparam P=3333,CAPTURE_START=121,LEASE_CYCLES=3320,WARM=40,MEASURE=240;
 reg clk=0;always #4 clk=~clk;
 reg rst_n=0,source_valid=0;reg [1:0] source_bank=0;reg [31:0] source_id=0;
 wire source_ready;wire [BANKS-1:0] writable;wire release_valid;wire [BANKS-2:0] released_bank;
 reg display_request_valid=0,display_done_valid=0,display_done_bank=0;
 wire display_request_ready,display_grant_valid,processing,pending,display_active,write_bank,front_bank;
 wire [27:0] display_base;wire [31:0] display_crc,display_id,completed,last_cycles;wire failed;wire [7:0] fault;
 hdmi_camera_fisheye_bank #(.WIDTH(32),.HEIGHT(8),.BANK_STRIDE(1048576)) dut(
 .clk(clk),.rst_n(rst_n),.cfg_corrected(1'b1),
 .source_valid(source_valid),.source_ready(source_ready),.source_bank(source_bank),.source_id(source_id),
 .source_writable(writable),.source_released(release_valid),.released_bank(released_bank),
 .display_request_valid(display_request_valid),.display_request_ready(display_request_ready),.display_grant_valid(display_grant_valid),.display_grant_ready(1'b1),
 .display_base(display_base),.display_crc(display_crc),.display_id(display_id),.display_done_valid(display_done_valid),.display_done_bank(display_done_bank),
 .arready(1'b0),.rdata(256'd0),.rvalid(1'b0),.rlast(1'b0),.rid(4'd0),.awready(1'b0),.wready(1'b0),.wlast(1'b0),
 .processing(processing),.pending(pending),.display_active(display_active),.write_bank(write_bank),.front_bank(front_bank),
 .completed_frames(completed),.last_cycles(last_cycles),.failed(failed),.fault(fault));
 integer cyc=0,phase=0,out_period=P,process_delay=2252,i,b,current_capture=-1,capture_id=0,next_id=1,head=0,tail=0;
 integer qbank[0:999],qid[0:999];integer owned[0:2];integer q_capture_end[0:999];integer started,accepted,drops,captures,shown,repeats,last_display_id=0;
 integer last_grant=-100000,lease_bank,lease_end=-1,max_residence=0;
 reg consumed=0,grant_seen=0;integer consumed_bank;
 always @(posedge clk)begin
   consumed=source_valid&&source_ready;
   if(rst_n&&completed>0&&last_cycles!=process_delay+1)$fatal(1,"stub latency does not match requested budget actual=%0d expected=%0d",last_cycles,process_delay+1);
   if(rst_n&&failed)$fatal(1,"bank failed %h cycle %0d",fault,cyc);
   if(rst_n&&processing&&display_active&&write_bank==front_bank)$fatal(1,"result ownership overlap");
 end
 initial begin
   if(!$value$plusargs("PHASE=%d",phase))phase=0;
   if(!$value$plusargs("OUT_PERIOD=%d",out_period))out_period=P;
   if(!$value$plusargs("PROCESS=%d",process_delay))process_delay=2252;
   for(i=0;i<3;i=i+1)owned[i]=0;
   started=0;accepted=0;drops=0;captures=0;shown=0;repeats=0;
   repeat(6)@(negedge clk);rst_n=1;
   for(cyc=0;cyc<(WARM+MEASURE)*P;cyc=cyc+1)begin
     @(negedge clk);
     display_request_valid=0;display_done_valid=0;
     if(consumed)begin
       if(head==tail || source_id!=qid[head] || source_bank!=qbank[head])$fatal(1,"descriptor mismatch");
       if(cyc>=WARM*P)accepted=accepted+1;
       head=head+1;
     end
     if(release_valid)begin
       if(!owned[released_bank])$fatal(1,"source release unowned");
       owned[released_bank]=0;
     end
     if(display_grant_valid&&!grant_seen)begin
       grant_seen=1;lease_end=cyc+LEASE_CYCLES;lease_bank=(display_base/1048576)-2;
       if(display_id<last_display_id)$fatal(1,"display went backward");
       if(cyc>=WARM*P)begin
          if(display_id>last_display_id)shown=shown+1;else repeats=repeats+1;
       end
       last_display_id=display_id;
     end
     if(!display_grant_valid)grant_seen=0;
     if(cyc==lease_end)begin display_done_valid=1;display_done_bank=lease_bank;end
     if(cyc%out_period==phase)begin
       if(display_request_ready)display_request_valid=1;
     end
     if(cyc%P==0&&current_capture>=0)begin
       if(tail>=1000)$fatal(1,"queue overflow");
       qbank[tail]=current_capture;qid[tail]=capture_id;q_capture_end[tail]=cyc;tail=tail+1;
       current_capture=-1;
       if(cyc>=WARM*P)captures=captures+1;
     end
     if(cyc%P==CAPTURE_START)begin
       b=-1;
       for(i=BANKS-1;i>=0;i=i-1)if(!owned[i]&&writable[i])b=i;
       if(b>=0)begin owned[b]=1;current_capture=b;capture_id=next_id;next_id=next_id+1;if(cyc>=WARM*P)started=started+1;end
       else if(cyc>=WARM*P)drops=drops+1;
     end
     source_valid=head<tail;
     if(source_valid)begin source_bank=qbank[head];source_id=qid[head];end
   end
   $display("SCHED_RESULT banks=%0d phase=%0d process=%0d out_period=%0d captured=%0d accepted=%0d shown=%0d repeats=%0d no_bank=%0d measured_process=%0d",BANKS,phase,process_delay,out_period,captures,accepted,shown,repeats,drops,last_cycles);
   $finish;
 end
endmodule
