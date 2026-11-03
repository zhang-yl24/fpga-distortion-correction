`timescale 1ns/1ps
module probe_case #(parameter MODE=0)(output reg finished=0);
 reg clk=0;always #4 clk=~clk;
 reg rst_n=0,init_done=0;initial begin repeat(5)@(negedge clk);rst_n=1;repeat(3)@(negedge clk);init_done=1;end
 wire[27:0]awaddr,araddr;wire[3:0]awlen,arlen;wire awvalid,arvalid,awready,arready,wready,wlast,rvalid,rlast;wire[255:0]wdata,rdata;wire[31:0]wstrb;wire[3:0]rid;
 wire started,done,failed;wire[7:0]fault;wire[3:0]phase;wire[1:0]grp;
 wire[31:0]writes,reads,read_beats,data_error_beats,protocol_errors,timeouts,crc_error_groups;
 wire[95:0]cnt,wmn,wmx,wsm,fmn,fmx,fsm,lmn,lmx,lsm,crc_a,crc_e;
 ddr_ui_service_probe #(.READS_PER_GROUP(16),.TIMEOUT_CYCLES(MODE==3 ? 32:128),.GAP_CYCLES(2)) dut(
  .clk(clk),.rst_n(rst_n),.init_done(init_done),.awaddr(awaddr),.araddr(araddr),.awlen(awlen),.arlen(arlen),.awvalid(awvalid),.arvalid(arvalid),.awready(awready),.arready(arready),
  .wdata(wdata),.wstrb(wstrb),.wready(wready),.wlast(wlast),.rdata(rdata),.rvalid(rvalid),.rlast(rlast),.rid(rid),
  .started(started),.done(done),.failed(failed),.fault(fault),.phase(phase),.active_group(grp),.writes(writes),.reads(reads),.read_beats(read_beats),.data_error_beats(data_error_beats),.protocol_errors(protocol_errors),.timeouts(timeouts),.crc_error_groups(crc_error_groups),
  .group_count(cnt),.ar_wait_min(wmn),.ar_wait_max(wmx),.ar_wait_sum(wsm),.first_min(fmn),.first_max(fmx),.first_sum(fsm),.last_min(lmn),.last_max(lmx),.last_sum(lsm),.actual_crc(crc_a),.expected_crc(crc_e));
 reg[255:0]mem[0:255];reg[27:0]wb=0,rb=0;reg wa=0,ra=0;integer wi=0,ri=0,lat=0,cycle=0,hold=0;reg release_timeout=0;
 wire acceptw=awvalid&&awready,acceptr=arvalid&&arready;
 wire writing=wa||acceptw;wire reading=ra||acceptr;
 wire[27:0]wbase=acceptw ? awaddr:wb,rbase=acceptr ? araddr:rb;
 wire[3:0]widx=acceptw ? 0:wi,ridx=acceptr ? 0:ri;
 assign awready=!wa&&!ra && (MODE!=1 || cycle%3!=0);
 assign arready=!wa&&!ra && (MODE!=3 || release_timeout) && (MODE!=1 || cycle%4!=0);
 assign wready=writing && (MODE!=1 || cycle%4!=0);
 assign wlast=widx==15;
 assign rvalid=(acceptr && MODE!=1) || (ra && lat==0 && (MODE!=1 || cycle%3!=0));
 assign rlast=(MODE==4 && reads==0) ? ridx==3:ridx==15;
 assign rid=(MODE==5 && reads==0 && ridx==0) ? 4'hf:0;
 function integer ix(input[27:0]a);begin ix=((a>>25)&7)*32+((a>>10)&1)*16+((a&1023)>>3);end endfunction
 wire corrupt=MODE==2 && grp==2 && reads==47 && ridx==0;
 assign rdata=rvalid ? (mem[ix(rbase+ridx*8)] ^ (corrupt ? 256'd1:256'd0)):256'd0;
 integer lane,i;
 reg prev_av=0,prev_ar=0;reg[27:0]prev_awaddr,prev_araddr;
 integer ref_wait=0,ref_accept=0,ref_first=0,ref_group=0,delta=0;
 integer rc[0:2],rwmn[0:2],rwmx[0:2],rwsm[0:2],rfmn[0:2],rfmx[0:2],rfsm[0:2],rlmn[0:2],rlmx[0:2],rlsm[0:2];
 initial for(i=0;i<3;i=i+1)begin rc[i]=0;rwmn[i]=2147483647;rwmx[i]=0;rwsm[i]=0;rfmn[i]=2147483647;rfmx[i]=0;rfsm[i]=0;rlmn[i]=2147483647;rlmx[i]=0;rlsm[i]=0;end
 always @(posedge clk)begin
  cycle<=cycle+1;
  if(!rst_n)begin wa<=0;ra<=0;wi<=0;ri<=0;lat<=0;prev_av<=0;prev_ar<=0;end else begin
   if(prev_av && (!awvalid || awaddr!==prev_awaddr))$fatal(1,"AW withdrew or changed case%0d",MODE);
   if(prev_ar && (!arvalid || araddr!==prev_araddr))$fatal(1,"AR withdrew or changed case%0d",MODE);
   prev_av<=awvalid&&!awready;prev_ar<=arvalid&&!arready;prev_awaddr<=awaddr;prev_araddr<=araddr;
   if(acceptw)begin
    if(awlen!=15 || awaddr[6:0]!=0 || ((awaddr&1023)+127)>1023)$fatal(1,"write layout");
    wa<=1;wb<=awaddr;wi<=0;
   end
   if(wready)begin
    if(wstrb!==32'hffffffff)$fatal(1,"strobe");
    for(lane=0;lane<8;lane=lane+1)if(wdata[lane*32+:32]!==(32'hca09e667 ^ (wbase+widx*8+lane)))$fatal(1,"written pattern case%0d",MODE);
    mem[ix(wbase+widx*8)]<=wdata;
    if(widx==15)begin wa<=0;wi<=0;end else wi<=widx+1;
   end
   if(acceptr)begin
    if(writes!=16 || arlen!=15 || araddr[6:0]!=0)$fatal(1,"read-before-commit/layout");
    ra<=1;rb<=araddr;ri<=0;lat<=MODE==1 ? 7:0;
   end else if(ra&&lat!=0)lat<=lat-1;
   if(rvalid)begin if(rlast)begin ra<=0;ri<=0;end else ri<=ridx+1;end
   if(MODE==3 && failed && !release_timeout)begin
    if(!arvalid)$fatal(1,"timeout AR not held");
    hold<=hold+1;if(hold==8)release_timeout<=1;
   end
   if(arvalid&&!arready)ref_wait=ref_wait+1;
   if(acceptr)begin ref_accept=cycle;ref_group=grp;end
   if(rvalid)begin
    delta=cycle-ref_accept;if(ridx==0)ref_first=delta;
    if(rlast && MODE<2)begin
     rc[ref_group]=rc[ref_group]+1;
     if(ref_wait<rwmn[ref_group])rwmn[ref_group]=ref_wait;
     if(ref_wait>rwmx[ref_group])rwmx[ref_group]=ref_wait;
     rwsm[ref_group]=rwsm[ref_group]+ref_wait;
     if(ref_first<rfmn[ref_group])rfmn[ref_group]=ref_first;
     if(ref_first>rfmx[ref_group])rfmx[ref_group]=ref_first;
     rfsm[ref_group]=rfsm[ref_group]+ref_first;
     if(delta<rlmn[ref_group])rlmn[ref_group]=delta;
     if(delta>rlmx[ref_group])rlmx[ref_group]=delta;
     rlsm[ref_group]=rlsm[ref_group]+delta;
     ref_wait=0;
    end
   end
  end
 end
 initial begin
  if(MODE<2)begin
   wait(done);@(negedge clk);
   if(failed || writes!=16 || reads!=48 || read_beats!=768 || data_error_beats || protocol_errors || timeouts || crc_error_groups || crc_a!==crc_e)$fatal(1,"success ledger case%0d",MODE);
   for(i=0;i<3;i=i+1)begin
    if(cnt[i*32+:32]!=rc[i] || wmn[i*32+:32]!=rwmn[i] || wmx[i*32+:32]!=rwmx[i] || wsm[i*32+:32]!=rwsm[i] || fmn[i*32+:32]!=rfmn[i] || fmx[i*32+:32]!=rfmx[i] || fsm[i*32+:32]!=rfsm[i] || lmn[i*32+:32]!=rlmn[i] || lmx[i*32+:32]!=rlmx[i] || lsm[i*32+:32]!=rlsm[i])$fatal(1,"stats mismatch case%0d group%0d",MODE,i);
   end
   if(MODE==0 && (fmx!=0 || lmn!={3{32'd15}} || lmx!={3{32'd15}}))$fatal(1,"zero latency distance");
   $display("PROBE_CRC case=%0d actual=%024h expected=%024h",MODE,crc_a,crc_e);
   repeat(12)@(negedge clk);if(awvalid||arvalid||!done||failed)$fatal(1,"not finite idle");
  end else begin
   wait(failed);wait(!wa&&!ra&&!awvalid&&!arvalid);repeat(5)@(negedge clk);
   if(done)$fatal(1,"failure promoted to done");
   if(MODE==2 && (fault!=8'h05 || data_error_beats!=1 || crc_error_groups!=1))$fatal(1,"data/CRC fault");
   if(MODE==3 && (fault!=8'h01 || timeouts!=1 || hold<8))$fatal(1,"timeout fault");
   if((MODE==4||MODE==5) && (fault!=8'h03 || protocol_errors==0))$fatal(1,"read protocol fault");
  end
  $display("PROBE_CASE_PASS mode=%0d writes=%0d reads=%0d beats=%0d fault=%02h",MODE,writes,reads,read_beats,fault);finished=1;
 end
 initial begin #1000000;$fatal(1,"bench deadline case%0d phase%0d",MODE,phase);end
endmodule
module tb_ddr_ui_service_probe;
 wire[5:0]done;
 probe_case #(.MODE(0))c0(done[0]);probe_case #(.MODE(1))c1(done[1]);probe_case #(.MODE(2))c2(done[2]);
 probe_case #(.MODE(3))c3(done[3]);probe_case #(.MODE(4))c4(done[4]);probe_case #(.MODE(5))c5(done[5]);
 initial begin wait(&done);$display("DDR_SERVICE_PROBE_SHORT_PASS cases=6 samecycle=1 stalls=1 atomic_stats=1 data_crc=1 held_timeout=1 protocol=1 finite=1");$finish;end
endmodule
