`timescale 1ns/1ps
module tb_tagpack #(parameter PACK=1,BAD=0,FINAL=0,W=1920,H=1080,TW=25,STRIDE=2,HEAD=0,COMPACT=1,IB=7);
reg clk=0;always #4 clk=~clk;
reg rst_n=0,fv=0,iv=0,oready=0;reg [TW-1:0] tag=0;
wire fr,ir,ov,failed;wire [7:0] fault;wire [TW-1:0] otag;
wire rfr,rir,rov,rfail;wire [7:0] rfault;wire [TW-1:0] rtag;
wire [23:0] a,b,c,d,ra,rb,rc,rd;wire [7:0] fx,fy,rfx,rfy;
wire [31:0] hits,misses,done,rhits,rmisses,rdone;
reg [TW-1:0] expected[0:4095];integer sent=0,received=0,cy=0;
`define CONFIG .WIDTH(W),.HEIGHT(H),.INDEX_BITS(IB),.TAG_W(TW),.QUERY_DEPTH(4096),.LOOKAHEAD(512),.TIMEOUT_BITS(26),.AREA_PROFILE(2),.COMPACT_COORDS(COMPACT),.HEAD_PREDECODE(HEAD),.CACHE_ROW_STRIDE(STRIDE),.CANDIDATE_KEY_PIPE(2),.LOCAL_INFLIGHT_MASK(1),.FILL_SCATTER8(1),.FILL_SCATTER16(1),.FILL_STREAM(1),.JOB_DONE_EDGE_SELECT(1)
`define INPUTS .clk(clk),.rst_n(rst_n),.frame_valid(fv),.frame_base(28'd0),.in_valid(iv),.in_x(-24'sd512),.in_y(-24'sd512),.in_tag(tag),.out_ready(oready),.arready(1'b0),.rdata(256'd0),.rvalid(1'b0),.rlast(1'b0),.rid(4'd0)
d256_runtime_prefetch_cache #(`CONFIG,.AF_AA_ORDINAL_TAG_PACK(PACK)) dut(`INPUTS,.frame_ready(fr),.in_ready(ir),.out_valid(ov),.out_tag(otag),.failed(failed),.fault(fault),.p00(a),.p10(b),.p01(c),.p11(d),.fx(fx),.fy(fy),.hits(hits),.misses(misses),.completed_queries(done));
cache_AA #(`CONFIG) ref_dut(`INPUTS,.frame_ready(rfr),.in_ready(rir),.out_valid(rov),.out_tag(rtag),.failed(rfail),.fault(rfault),.p00(ra),.p10(rb),.p01(rc),.p11(rd),.fx(rfx),.fy(rfy),.hits(rhits),.misses(rmisses),.completed_queries(rdone));
always @(posedge clk)begin
 cy=cy+1;
 if(rst_n && BAD==0)begin
  if({fr,ir,ov,failed,fault,hits,misses,done} !== {rfr,rir,rov,rfail,rfault,rhits,rmisses,rdone})$fatal(1,"cycle compatibility");
  if(ov && {otag,a,b,c,d,fx,fy} !== {rtag,ra,rb,rc,rd,rfx,rfy})$fatal(1,"output compatibility");
  if(iv && ir)begin expected[sent]=tag;sent=sent+1;end
  if(ov && oready)begin if(otag!==expected[received])$fatal(1,"tag roundtrip");received=received+1;end
  if(failed)$fatal(1,"unexpected fault %h",fault);
 end
 if(cy>20000)$fatal(1,"timeout");
end
always @(negedge clk) oready=(cy>700 && cy%7!=0 && cy%11!=0);
task send(input [TW-1:0] value);begin
 @(negedge clk);iv=1;tag=value;
 @(posedge clk);while(!ir)@(posedge clk);
 @(negedge clk);iv=0;
end endtask
integer i,rows,group_size,macro_x,local_n,x,y,replacements=0,empty_loads=0;
always @(posedge clk)if(rst_n && dut.head_load)begin
 if(dut.store_query_accept)replacements=replacements+1;else empty_loads=empty_loads+1;
 if(dut.fifo_head_tag[5:0] !== {dut.af_next_head_ordinal[8:6],dut.af_next_head_ordinal[2:0]} && PACK)$fatal(1,"head ordinal bits");
end
initial begin
 #1;
 if(PACK==0 && dut.FIFO_TAG_W!=TW)$fatal(1,"generic width");
 if(PACK==1 && W==1920 && H==1080 && TW==25 && STRIDE==2 && HEAD==0 && COMPACT==1 && IB==7)begin
  if(dut.TOKEN_W!=54 || $bits(dut.skid_tag[0])!=25 || $bits(dut.decoded_tag)!=25 || $bits(dut.head_tag)!=25 || $bits(otag)!=25)$fatal(1,"AF widths");
 end
 if(PACK==0 && TW==25 && COMPACT==1 && HEAD==0 && W==1920 && H==1080 && dut.TOKEN_W!=63)$fatal(1,"AA width");
 repeat(4)@(negedge clk);rst_n=1;
 @(negedge clk);fv=1;@(posedge clk);while(!fr)@(posedge clk);@(negedge clk);fv=0;
 if(BAD!=0)begin
  @(negedge clk);iv=1;tag=(25'b1<<(BAD-1));#1;
  if(BAD>=22)begin
   if(!ir || !dut.af_tag_reject || dut.skid_push)$fatal(1,"bad high tag not rejected before skid");
  end else if(!ir || !dut.skid_push)$fatal(1,"low tag should reach decoded guard");
  @(posedge clk);#1;
  if(BAD<22)begin
   @(negedge clk);iv=0;
   wait(dut.decoded_valid);#1;
   if(!dut.af_decoded_tag_bad || dut.scout_commit)$fatal(1,"bad decoded tag admitted");
   @(posedge clk);#1;
  end
  if(!failed || fault!==8'h4a || dut.admitted_count!=0)$fatal(1,"bad tag must fault without FIFO admission");
  repeat(4)@(negedge clk);
  if(!failed || ir || ov || dut.query_fifo.total!=0)$fatal(1,"quarantine");
  $display("PASS_BAD_TAG bit=%0d",BAD-1);$finish;
 end
 rows=FINAL ? 24:32;group_size=64*rows;
 if(PACK)begin
  for(i=0;i<2*group_size;i=i+1)begin
   macro_x=(i/group_size)*64;local_n=i%group_size;
   x=macro_x+((local_n/64)%8)*8+(local_n%8);
   y=(FINAL ? 1056:0)+(local_n/512)*8+((local_n/8)%8);
   send(((i%3)==0 ? 25'h1000000:0)+y*1920+x);
  end
 end else begin
  send(25'h0000000);send(25'h01fa3ff);send(25'h1000000);send(25'h11fa3ff);
  send(25'h01fffff);send(25'h11fffff);send(25'h0200000);send(25'h0400000);send(25'h0800000);send(25'h1ffffff);
 end
 wait(received==sent);repeat(3)@(negedge clk);
 if(PACK && (replacements==0 || empty_loads==0))$fatal(1,"missing head-load timing cases");
 $display("PASS_ROUNDTRIP pack=%0d token=%0d sent=%0d cycles=%0d replacements=%0d empty_loads=%0d",PACK,dut.TOKEN_W,sent,cy,replacements,empty_loads);$finish;
end
endmodule
