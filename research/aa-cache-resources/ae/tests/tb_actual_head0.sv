`timescale 1ns/1ps
module tb_full_cache_ab #(parameter STRIDE=2,HEAD1=0);
 // Actual AA production configuration, not hypothetical HEAD1.
 initial begin
  if(HEAD1!=0 || STRIDE!=2)$fatal(1,"actual AA requires HEAD0/STRIDE2");
  #1;
  if(ref_dut.TOKEN_W!=63 || cand_dut.TOKEN_W!=63 || $bits(cand_dut.head_tag)!=25)$fatal(1,"actual AA FIFO63/TAG25 binding failed");
 end
 reg clk=0;always #4 clk=~clk;
 reg rst_n=0,frame_valid=0,in_valid=0,out_ready=0,arready=0,rvalid=0,rlast=0;
 reg [27:0] frame_base=0;
 reg signed [23:0] in_x=0,in_y=0;reg [24:0] in_tag=0;
 reg [255:0] rdata=0;reg [3:0] rid=0;
 wire fr0,fr1,ir0,ir1,ov0,ov1,av0,av1,fail0,fail1;
 wire [23:0] p000,p100,p010,p110,p001,p101,p011,p111; wire [24:0] tag0,tag1;
 wire [7:0] fx0,fy0,fx1,fy1,fault0,fault1;
 wire [27:0] aa0,aa1;wire [3:0] al0,al1;
 wire [31:0] hit0,hit1,miss0,miss1,done0,done1;
 cache_baseline #(.WIDTH(1920),.HEIGHT(1080),.INDEX_BITS(7),.TAG_W(25),.TIMEOUT_BITS(26),.QUERY_DEPTH(4096),.LOOKAHEAD(512),.AREA_PROFILE(2),.CANDIDATE_KEY_PIPE(2),.HEAD_PREDECODE(HEAD1),.LOCAL_INFLIGHT_MASK(1),.COMPACT_COORDS(1),.FILL_SCATTER8(1),.FILL_SCATTER16(1),.FILL_STREAM(1),.JOB_DONE_EDGE_SELECT(1),.READ_REQUEST_LOOKAHEAD(0),.CACHE_ROW_STRIDE(STRIDE)) ref_dut(
 .clk(clk),.rst_n(rst_n),.frame_valid(frame_valid),.frame_ready(fr0),.frame_base(frame_base),.in_valid(in_valid),.in_ready(ir0),.in_x(in_x),.in_y(in_y),.in_tag(in_tag),.out_valid(ov0),.out_ready(out_ready),.p00(p000),.p10(p100),.p01(p010),.p11(p110),.fx(fx0),.fy(fy0),.out_tag(tag0),.araddr(aa0),.arlen(al0),.arvalid(av0),.arready(arready),.rdata(rdata),.rvalid(rvalid),.rlast(rlast),.rid(rid),.failed(fail0),.fault(fault0),.hits(hit0),.misses(miss0),.completed_queries(done0));
 cache_fallback #(.WIDTH(1920),.HEIGHT(1080),.INDEX_BITS(7),.TAG_W(25),.TIMEOUT_BITS(26),.QUERY_DEPTH(4096),.LOOKAHEAD(512),.AREA_PROFILE(2),.CANDIDATE_KEY_PIPE(2),.HEAD_PREDECODE(HEAD1),.LOCAL_INFLIGHT_MASK(1),.COMPACT_COORDS(1),.FILL_SCATTER8(1),.FILL_SCATTER16(1),.FILL_STREAM(1),.JOB_DONE_EDGE_SELECT(1),.READ_REQUEST_LOOKAHEAD(0),.CACHE_ROW_STRIDE(STRIDE)) cand_dut(
 .clk(clk),.rst_n(rst_n),.frame_valid(frame_valid),.frame_ready(fr1),.frame_base(frame_base),.in_valid(in_valid),.in_ready(ir1),.in_x(in_x),.in_y(in_y),.in_tag(in_tag),.out_valid(ov1),.out_ready(out_ready),.p00(p001),.p10(p101),.p01(p011),.p11(p111),.fx(fx1),.fy(fy1),.out_tag(tag1),.araddr(aa1),.arlen(al1),.arvalid(av1),.arready(arready),.rdata(rdata),.rvalid(rvalid),.rlast(rlast),.rid(rid),.failed(fail1),.fault(fault1),.hits(hit1),.misses(miss1),.completed_queries(done1));
 integer cycle=0,stall_until=0,mem_delay=0,mem_beat=0,ar_count=0,out_count=0,max_fifo=0,triple_overlap=0;
 integer i,j,n,b,sent,x,y,frame_start,frame_done_target,seed=20261106; integer half_crossings=0; reg last_half=0;
 reg mem_live=0,allow_fault=0,inject_bad_id=0;reg [27:0] mem_addr=0;
 function [255:0] make_beat;
 input [27:0] a;input integer beat;integer l,p;begin
  for(l=0;l<16;l=l+1)begin p=a*2+beat*16+l;make_beat[l*16+:16]=(p*13+7)&65535;end
 end endfunction
 always @(negedge clk)begin
  if(!rst_n)begin arready=0;rvalid=0;rlast=0;out_ready=0;end
  else begin
   arready=!mem_live && cycle%7!=0;
   rvalid=mem_live && mem_delay==0 && cycle%31<25 && cycle%113<107;
   rlast=mem_beat==7;rdata=make_beat(mem_addr,mem_beat);rid=inject_bad_id ? 4'd1:4'd0;
   out_ready=cycle>=stall_until && cycle%257>=17 && cycle%9!=0;
  end
 end
 always @(posedge clk)begin
  cycle=cycle+1;
  if(!rst_n)begin mem_live=0;mem_delay=0;mem_beat=0;end
  else begin
   if(av0 && arready)begin mem_live=1;mem_addr=aa0;mem_delay=3;mem_beat=0;ar_count=ar_count+1;end
   else if(mem_live)begin
    if(mem_delay>0)mem_delay=mem_delay-1;
    else if(rvalid)begin if(mem_beat==7)begin mem_live=0;mem_beat=0;end else mem_beat=mem_beat+1;end
   end
   if(ov0 && out_ready)out_count=out_count+1;
  end
  #1;
  if(rst_n)begin
   if(ref_dut.retired_count[13] != last_half)half_crossings=half_crossings+1;
   last_half=ref_dut.retired_count[13];
   if({fr0,ir0,ov0,av0,fail0,fault0,hit0,miss0,done0} !== {fr1,ir1,ov1,av1,fail1,fault1,hit1,miss1,done1})begin
    $display("FAIL control cycle=%0d fr=%b%b ir=%b%b ov=%b%b ar=%b%b failed=%b%b fault=%h/%h",cycle,fr0,fr1,ir0,ir1,ov0,ov1,av0,av1,fail0,fail1,fault0,fault1);$fatal(1);
   end
   if(ref_dut.candidate_current && (ref_dut.candidate_first !== cand_dut.candidate_first || ref_dut.candidate_line !== cand_dut.candidate_line))$fatal(1,"candidate absolute identity mismatch");
   if(ref_dut.job_hold && {ref_dut.job_row,ref_dut.job_col} !== {cand_dut.job_row,cand_dut.job_col})$fatal(1,"held coordinates mismatch");
   if(ref_dut.job_hold && ref_dut.job_first !== cand_dut.job_first)$fatal(1,"held absolute first identity mismatch");
   if(av0 && {aa0,al0} !== {aa1,al1})$fatal(1,"DDR command mismatch");
   if(ov0 && {p000,p100,p010,p110,fx0,fy0,tag0} !== {p001,p101,p011,p111,fx1,fy1,tag1})$fatal(1,"pixel/tag mismatch");
   if(fail0 && !allow_fault)$fatal(1,"unexpected baseline/candidate fault %h",fault0);
   if({ref_dut.active_valid,ref_dut.pending_valid,ref_dut.active_generation} !== {cand_dut.active_valid,cand_dut.pending_valid,cand_dut.active_generation})$fatal(1,"directory flags mismatch");
   if(ref_dut.local_inflight_owned !== cand_dut.local_inflight_owned)$fatal(1,"inflight ownership mismatch");
   if({ref_dut.admitted_count,ref_dut.issued_count,ref_dut.retired_count} !== {cand_dut.admitted_count,cand_dut.issued_count,cand_dut.retired_count})$fatal(1,"identity counter mismatch");
   for(i=0;i<128;i=i+1)begin
    if(ref_dut.active_tag[i] !== cand_dut.active_tag[i])$fatal(1,"raw active tag mismatch line=%0d",i);
    if(ref_dut.pending_tag[i] !== cand_dut.pending_tag[i])$fatal(1,"raw pending tag mismatch line=%0d",i);
    if(ref_dut.active_last_use[i] !== cand_dut.active_last_use[i])$fatal(1,"raw active last-use mismatch line=%0d",i);
    if(ref_dut.pending_last_use[i] !== cand_dut.pending_last_use[i])$fatal(1,"raw pending last-use mismatch line=%0d",i);
    if(ref_dut.pending_first_use[i] !== cand_dut.pending_first_use[i])$fatal(1,"raw pending first-use mismatch line=%0d",i);
    if(ref_dut.active_valid[i] && (ref_dut.active_tag[i] !== cand_dut.active_tag[i] || ref_dut.active_busy[i] !== cand_dut.active_busy[i]))$fatal(1,"active tag/busy mismatch line=%0d",i);
    if(cand_dut.active_valid[i] && cand_dut.active_busy[i] && ((cand_dut.active_last_use[i]-cand_dut.retired_count[12:0])&8191)>4101)$fatal(1,"active last-use window violated");
    if(cand_dut.pending_valid[i] && ((cand_dut.pending_last_use[i]-cand_dut.retired_count[12:0])&8191)>4101)$fatal(1,"pending last-use window violated");
    if(ref_dut.pending_valid[i] && {ref_dut.pending_tag[i],ref_dut.pending_first_use[i],ref_dut.pending_last_use[i]} !== {cand_dut.pending_tag[i],cand_dut.pending_first_use[i],cand_dut.pending_last_use[i]})$fatal(1,"pending state mismatch line=%0d",i);
    if(ref_dut.pending_valid[i] && ((ref_dut.pending_tag[i] / 15) !== (cand_dut.pending_tag[i] / 15) || (ref_dut.pending_tag[i] % 15) !== (cand_dut.pending_tag[i] % 15)))$fatal(1,"derived coordinates mismatch line=%0d",i);
   end
   if({ref_dut.new_ref,ref_dut.first_ref,ref_dut.scout_commit} !== {cand_dut.new_ref,cand_dut.first_ref,cand_dut.scout_commit})$fatal(1,"admission/write event mismatch");
   if(cand_dut.candidate_pending_tag_read !== cand_dut.pending_tag[cand_dut.candidate_line])$fatal(1,"candidate direct RAM read mismatch");
   if(cand_dut.job_pending_tag_read !== cand_dut.pending_tag[cand_dut.job_line])$fatal(1,"job direct RAM read mismatch");
   if(cand_dut.done_pending_tag_read !== cand_dut.pending_tag[cand_dut.inflight_line])$fatal(1,"done direct RAM read mismatch");
   for(j=0;j<4;j=j+1)begin
    if(cand_dut.decoded_bounds[j])begin
     if(cand_dut.scout_pending_tag_read[j] !== cand_dut.pending_tag[cand_dut.decoded_line_packed[j*7+:7]])$fatal(1,"W scout pending tag read mismatch");
     if(cand_dut.scout_active_tag_read[j] !== cand_dut.active_tag[cand_dut.decoded_line_packed[j*7+:7]])$fatal(1,"W scout active tag read mismatch");
     if(cand_dut.scout_pending_valid_read[j] !== cand_dut.pending_valid[cand_dut.decoded_line_packed[j*7+:7]])$fatal(1,"W scout pending valid read mismatch");
     if(cand_dut.scout_active_valid_read[j] !== cand_dut.active_valid[cand_dut.decoded_line_packed[j*7+:7]])$fatal(1,"W scout active valid read mismatch");
    end
    if(cand_dut.head_bounds[j])begin
     if(cand_dut.head_pending_tag_read[j] !== cand_dut.pending_tag[cand_dut.head_line[j]])$fatal(1,"W head pending tag read mismatch");
     if(cand_dut.head_active_tag_read[j] !== cand_dut.active_tag[cand_dut.head_line[j]])$fatal(1,"W head active tag read mismatch");
     if(cand_dut.head_pending_valid_read[j] !== cand_dut.pending_valid[cand_dut.head_line[j]])$fatal(1,"W head pending valid read mismatch");
     if(cand_dut.head_active_valid_read[j] !== cand_dut.active_valid[cand_dut.head_line[j]])$fatal(1,"W head active valid read mismatch");
    end
   end
   if(ref_dut.query_fifo.total>max_fifo)max_fifo=ref_dut.query_fifo.total;
   if(ref_dut.scout_commit && ref_dut.retire && ref_dut.fill_done_good)triple_overlap=triple_overlap+1;
  end
  if(cycle%20000==0)begin $display("PROGRESS cycle=%0d sent=%0d done=%0d target=%0d fifo=%0d",cycle,sent,done0,frame_done_target,ref_dut.query_fifo.total);$fflush();end
  if(cycle>400000)$fatal(1,"bounded test timeout");
 end
 task reset_duts;begin
  @(negedge clk);rst_n=0;frame_valid=0;in_valid=0;repeat(5)@(negedge clk);rst_n=1;repeat(3)@(negedge clk);
 end endtask
 task begin_frame;begin
  while(!fr0)@(negedge clk);
  frame_valid=1;@(negedge clk);frame_valid=0;
 end endtask
 task drive_query;
 input integer q,mode;
 begin
  if(mode==4)begin x=(q%8<4) ? 127:255;y=(q/8192)*64;end
  else if(mode==0 && q<4500)begin x=0;y=0;end
  else if(mode==0)begin x=(q*17)%1920;y=((q/32)*3)%1080;end
  else if(mode==1)begin x=(q%5==0)?127:((q%7==0)?255:0);y=3+64*((q/7)%3);end
  else begin
   x=(q*391)%1922-1;y=(q*83)%1082-1;
   if(q%19==0)x=-100;if(q%23==0)y=2000;
  end
  in_x=x*256+(q&255);in_y=y*256+((q*7)&255);in_tag={q[0],q[23:0]};
 end endtask
 task run_frame;
 input integer count,mode,stall;
 begin
  frame_start=cycle;frame_done_target=done0+count;stall_until=cycle+stall;begin_frame;sent=0;
  while(sent<count)begin
   @(negedge clk);in_valid=(cycle%13!=0);drive_query(sent,mode);
   @(posedge clk);if(in_valid && ir0)sent=sent+1;
  end
  @(negedge clk);in_valid=0;
  while(done0!=frame_done_target || !fr0)@(negedge clk);
  $display("PASS_FRAME mode=%0d queries=%0d cycles=%0d total_ar=%0d max_fifo=%0d triple_overlap=%0d",mode,count,cycle-frame_start,ar_count,max_fifo,triple_overlap);$fflush();
 end endtask
 integer writes_hist[0:4];integer bank_counts[0:3];integer wi,wb,ww;integer total_writes=0;
 initial begin for(wi=0;wi<5;wi=wi+1)writes_hist[wi]=0;end
 always @(posedge clk)if(rst_n && cand_dut.scout_commit)begin
  for(wb=0;wb<4;wb=wb+1)bank_counts[wb]=0;
  ww=0;
  for(wi=0;wi<4;wi=wi+1)if(cand_dut.new_ref[wi])begin
   wb={cand_dut.decoded_line_packed[wi*7+6],cand_dut.decoded_line_packed[wi*7]};
   bank_counts[wb]=bank_counts[wb]+1;ww=ww+1;
  end
  writes_hist[ww]=writes_hist[ww]+1;total_writes=total_writes+ww;
  if(STRIDE==2)for(wb=0;wb<4;wb=wb+1)if(bank_counts[wb]>1)$fatal(1,"multiple new pending writes per bank");
 end
 genvar bn;
 generate if(STRIDE==2)begin: command_checks
  for(bn=0;bn<4;bn=bn+1)begin: bank
   integer pp,chosen;
   always @(posedge clk)if(rst_n && cand_dut.scout_commit)begin
    chosen=-1;
    for(pp=0;pp<4;pp=pp+1)if(cand_dut.new_ref[pp] && {cand_dut.decoded_line_packed[pp*7+6],cand_dut.decoded_line_packed[pp*7]}==bn)chosen=pp;
    if(cand_dut.pending_tag_banked_storage.bank_memory[bn].write_valid !== (chosen>=0))$fatal(1,"bank write valid mismatch");
    if(chosen>=0 && (cand_dut.pending_tag_banked_storage.bank_memory[bn].write_address !== cand_dut.decoded_line_packed[chosen*7+1+:5] || cand_dut.pending_tag_banked_storage.bank_memory[bn].write_tag !== cand_dut.decoded_block[chosen]))$fatal(1,"bank write command mismatch");
   end
  end
 end endgenerate
 integer join_publish_count=0,publish_other_writes=0,pending_last_write_count=0;
 always @(posedge clk)if(rst_n && !cand_dut.failed)begin
  if(cand_dut.publishing_pending_join !== cand_dut.add_pending[cand_dut.inflight_line])$fatal(1,"pending publication join bypass mismatch");
  if(cand_dut.publishing_pending_last !== cand_dut.pending_last_use[cand_dut.inflight_line])$fatal(1,"publishing pending RAM read mismatch");
  if(cand_dut.fill_done_good && cand_dut.add_pending[cand_dut.inflight_line])join_publish_count=join_publish_count+1;
  if(cand_dut.fill_done_good && (|(cand_dut.add_pending & ~cand_dut.publishing_line)))publish_other_writes=publish_other_writes+1;
  if(cand_dut.scout_commit)for(integer pp=0;pp<4;pp=pp+1)if(cand_dut.pending_last_admission[pp])pending_last_write_count=pending_last_write_count+1;
 end
 integer select_phase_checks=0,held_phase_checks=0,selects=0,accepts=0,accept_done=0,select_done=0,hold_switches=0;
 reg last_hold=0;
 always @(posedge clk)if(rst_n && !cand_dut.failed)begin
  if(cand_dut.scheduler_line !== (cand_dut.job_hold ? cand_dut.job_line:cand_dut.candidate_line))$fatal(1,"scheduler address mismatch");
  if(cand_dut.scheduler_pending_tag !== cand_dut.pending_tag[cand_dut.scheduler_line])$fatal(1,"scheduler tag read mismatch");
  if(cand_dut.scheduler_first_low !== cand_dut.pending_first_use[cand_dut.scheduler_line])$fatal(1,"scheduler first read mismatch");
  if(!ref_dut.job_hold)begin
   select_phase_checks=select_phase_checks+1;
   if(ref_dut.candidate_current !== cand_dut.candidate_current)$fatal(1,"candidate phase current mismatch");
   if(cand_dut.scheduler_pending_tag !== ref_dut.candidate_pending_tag_read)$fatal(1,"candidate phase tag mismatch");
  end else begin
   held_phase_checks=held_phase_checks+1;
   if(ref_dut.job_current !== cand_dut.job_current)$fatal(1,"held phase current mismatch");
   if(cand_dut.scheduler_pending_tag !== ref_dut.job_pending_tag_read)$fatal(1,"held phase tag mismatch");
  end
  if(ref_dut.fill_done_good !== cand_dut.fill_done_good)$fatal(1,"done port identity mismatch");
  if(ref_dut.fill_accept !== cand_dut.fill_accept)$fatal(1,"fill accept mismatch");
  if(ref_dut.job_hold !== cand_dut.job_hold)$fatal(1,"job hold mismatch");
  if(ref_dut.job_hold && {ref_dut.job_first,ref_dut.job_ticket} !== {cand_dut.job_first,cand_dut.job_ticket})$fatal(1,"full held identity mismatch");
  if(!ref_dut.job_hold && ref_dut.job_select_window && ref_dut.candidate_current)selects=selects+1;
  if(ref_dut.fill_accept)accepts=accepts+1;
  if(ref_dut.fill_accept && ref_dut.fill_done_good)accept_done=accept_done+1;
  if(!ref_dut.job_hold && ref_dut.job_select_window && ref_dut.candidate_current && ref_dut.fill_done_good)select_done=select_done+1;
  if(last_hold !== cand_dut.job_hold)hold_switches=hold_switches+1;
  last_hold=cand_dut.job_hold;
 end

 function [7:0] oracle_code;
 input [13:0] tag;reg [10:0] row;reg [3:0] col;
 begin row=tag/15;col=tag%15;oracle_code={row[10:6],col[3:1]};end
 endfunction
 integer code_scout=0,code_head=0,code_sched=0,code_done=0,code_write=0,code_publish=0;
 integer xcarry=0,ycarry=0;
 generate if(STRIDE==2)begin: codec_checks
  for(genvar cb=0;cb<4;cb=cb+1)begin: bank
   for(genvar cw=0;cw<32;cw=cw+1)begin: word
    localparam CL=(cb/2)*64+cw*2+(cb%2);
    always @(negedge clk)if(rst_n)begin
     if($bits(cand_dut.pending_tag_banked_storage.bank_memory[cb].words[cw])!=8 || $bits(cand_dut.pending_tag_banked_storage.bank_memory[cb].active_tags[cw])!=8)$fatal(1,"physical directory word not8");
     if(ref_dut.pending_valid[CL])begin
      if(cand_dut.pending_tag_banked_storage.bank_memory[cb].words[cw] !== oracle_code(ref_dut.pending_tag[CL]))$fatal(1,"pending physical code mismatch line=%0d",CL);
      if(cand_dut.native_tag8_expand(CL,cand_dut.pending_tag_banked_storage.bank_memory[cb].words[cw]) !== ref_dut.pending_tag[CL])$fatal(1,"pending full identity mismatch line=%0d",CL);
     end
     if(ref_dut.active_valid[CL])begin
      if(cand_dut.pending_tag_banked_storage.bank_memory[cb].active_tags[cw] !== oracle_code(ref_dut.active_tag[CL]))$fatal(1,"active physical code mismatch line=%0d",CL);
      if(cand_dut.native_tag8_expand(CL,cand_dut.pending_tag_banked_storage.bank_memory[cb].active_tags[cw]) !== ref_dut.active_tag[CL])$fatal(1,"active full identity mismatch line=%0d",CL);
     end
    end
   end
   always @(posedge clk)if(rst_n && cand_dut.scout_commit && cand_dut.pending_tag_banked_storage.bank_memory[cb].write_valid)
    if(cand_dut.pending_tag_banked_storage.bank_memory[cb].write_code !== oracle_code(cand_dut.pending_tag_banked_storage.bank_memory[cb].write_tag))$fatal(1,"actual bank write code mismatch");
  end
  always @(posedge clk)if(rst_n && !cand_dut.failed)begin
   for(integer cp=0;cp<4;cp=cp+1)begin
    if(cand_dut.decoded_bounds[cp])begin
     code_scout=code_scout+1;
     if(cand_dut.decoded_dir_code[cp] !== oracle_code(ref_dut.decoded_block[cp]))$fatal(1,"scout neighbour provenance mismatch");
     if(cand_dut.scout_pending_valid_read[cp] &&
       ((cand_dut.scout_pending_dir_read[cp]==cand_dut.decoded_dir_code[cp]) !== (ref_dut.scout_pending_tag_read[cp]==ref_dut.decoded_block[cp])))$fatal(1,"scout pending functional comparison mismatch");
     if(cand_dut.scout_active_valid_read[cp] &&
       ((cand_dut.scout_active_dir_read[cp]==cand_dut.decoded_dir_code[cp]) !== (ref_dut.scout_active_tag_read[cp]==ref_dut.decoded_block[cp])))$fatal(1,"scout active functional comparison mismatch");
    end
    if(cand_dut.head_bounds[cp])begin
     code_head=code_head+1;
     if(cand_dut.head_dir_code[cp] !== oracle_code(ref_dut.head_block[cp]))$fatal(1,"head neighbour provenance mismatch");
     if(cand_dut.head_pending_valid_read[cp] &&
       ((cand_dut.head_pending_dir_read[cp]==cand_dut.head_dir_code[cp]) !== (ref_dut.head_pending_tag_read[cp]==ref_dut.head_block[cp])))$fatal(1,"head pending functional comparison mismatch");
     if(cand_dut.head_active_valid_read[cp] &&
       ((cand_dut.head_active_dir_read[cp]==cand_dut.head_dir_code[cp]) !== (ref_dut.head_active_tag_read[cp]==ref_dut.head_block[cp])))$fatal(1,"head active functional comparison mismatch");
    end
    if(cand_dut.scout_commit && cand_dut.new_ref[cp])code_write=code_write+1;
   end
   if(cand_dut.scheduler_pending_valid)begin
    code_sched=code_sched+1;
    if(cand_dut.scheduler_functional_tag !== ref_dut.scheduler_pending_tag)$fatal(1,"functional scheduler full-tag mismatch");
    if(cand_dut.scheduler_functional_row !== ref_dut.scheduler_pending_tag/15 || cand_dut.scheduler_functional_col !== ref_dut.scheduler_pending_tag%15)$fatal(1,"functional scheduler coordinates mismatch");
   end
   if(cand_dut.control_done_pending_valid)begin
    code_done=code_done+1;
    if(cand_dut.done_functional_tag !== ref_dut.done_pending_tag_read)$fatal(1,"functional done full-tag mismatch");
   end
   if(cand_dut.fill_done_good)code_publish=code_publish+1;
   if(cand_dut.scout_commit && &cand_dut.decoded_x[14:8])xcarry=xcarry+1;
   if(cand_dut.scout_commit && &cand_dut.decoded_y[13:8])ycarry=ycarry+1;
  end
 end endgenerate
 initial begin
  reset_duts;
  run_frame(25000,4,6000);
  run_frame(1000,1,0);
  run_frame(1000,2,0);
  if(half_crossings<3)$fatal(1,"missing query-ID half-circle crossings: %0d",half_crossings);
  if(max_fifo!=4096)$fatal(1,"did not cover full query FIFO: %0d",max_fifo);
  // Existing DDR bad-ID quarantine and reset recovery must remain equivalent.
  reset_duts;allow_fault=1;inject_bad_id=1;begin_frame;
  @(negedge clk);in_valid=1;drive_query(0,0);
  @(posedge clk);while(!ir0)@(posedge clk);
  @(negedge clk);in_valid=0;
  while(!fail0)@(negedge clk);
  repeat(30)@(negedge clk);
  $display("PASS_FAULT bad_id code=%h quarantine=30",fault0);
  inject_bad_id=0;reset_duts;allow_fault=0;
  run_frame(100,2,0);
  $display("PASS_WINDOW_CROSSINGS count=%0d FIRST_W=%0d",half_crossings,cand_dut.FIRST_W);
  if(STRIDE==2 && writes_hist[4]==0)$fatal(1,"no four simultaneous bank writes covered");
  $display("PASS_BANK_WRITES stride=%0d head1=%0d count=%0d hist0=%0d hist1=%0d hist2=%0d hist3=%0d hist4=%0d",STRIDE,HEAD1,total_writes,writes_hist[0],writes_hist[1],writes_hist[2],writes_hist[3],writes_hist[4]);
  if(join_publish_count==0)$fatal(1,"missing join+publish bypass coverage");
  $display("PASS_PENDING_LAST_BYPASS join_publish=%0d publish_other_writes=%0d pending_writes=%0d",join_publish_count,publish_other_writes,pending_last_write_count);
  if(select_phase_checks==0 || held_phase_checks==0 || selects==0 || accepts==0 || hold_switches==0)$fatal(1,"missing scheduler phase coverage");
  $display("PASS_SCHEDULER_PORT select_checks=%0d held_checks=%0d selections=%0d accepts=%0d accept_done=%0d select_done=%0d hold_switches=%0d",select_phase_checks,held_phase_checks,selects,accepts,accept_done,select_done,hold_switches);
  if(STRIDE==2 && (code_scout==0 || code_head==0 || code_sched==0 || code_done==0 || code_write==0 || code_publish==0 || xcarry==0 || ycarry==0))$fatal(1,"missing functional codec/carry coverage");
  $display("PASS_TAG8_FUNCTIONAL enabled=%0d scout=%0d head=%0d scheduler=%0d done=%0d writes=%0d publish=%0d xcarry=%0d ycarry=%0d",STRIDE==2,code_scout,code_head,code_sched,code_done,code_write,code_publish,xcarry,ycarry);
  $display("PASS_FULL_CACHE_AB queries=27100 frames=4 outputs=%0d ar=%0d max_fifo=%0d triple_overlap=%0d cycles=%0d baseline=AA_ff5e551c candidate=AE_7a34f75e HEAD0_TAG25_FIFO63",out_count,ar_count,max_fifo,triple_overlap,cycle);
  $finish;
 end
endmodule
