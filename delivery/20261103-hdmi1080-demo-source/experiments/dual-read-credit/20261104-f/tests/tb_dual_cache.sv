`timescale 1ns/1ps
module tb_dual_cache;
reg clk=0;always #4 clk=~clk;reg rst_n=0;
reg frame_valid=0;wire frame_ready;reg [27:0] frame_base=0;
reg iv=0;wire ir;reg signed [23:0] ix=0,iy=0;reg [23:0] itag=0;
wire ov;reg ore=1;wire [23:0] p00,p10,p01,p11,otag;wire [7:0] fx,fy;
wire [27:0] ca,araddr;wire [3:0] cl,arlen;wire cv,cr,arvalid,arready;
wire [255:0] cd,rdata;wire rv,rl,crv,crl;wire [3:0] rid,crid;
wire failed,arbfailed,arbbusy;wire [7:0] fault,arbfault;wire [31:0] hits,misses,queries,b0,b1;
wire [27:0] memaddr;wire [255:0] memdata;
wire unused_awready,unused_wready,unused_wlast,unused_memwe,unused_ref,unused_stop;
wire [27:0] unused_memwa;wire [255:0] unused_memwd;wire [31:0] unused_memws;
wire [63:0] tick,nar,naw,nr,nw,nref,nstop,nturn;
d256_runtime_prefetch_cache #(.WIDTH(1920),.HEIGHT(1080),.INDEX_BITS(6),.TAG_W(24),.QUERY_DEPTH(512),.LOOKAHEAD(256),
 .COMPACT_COORDS(1),.AREA_PROFILE(2),.CANDIDATE_KEY_PIPE(2),.HEAD_PREDECODE(1),.LOCAL_INFLIGHT_MASK(1),
 .FILL_STREAM(1),.FILL_SCATTER16(1),.FILL_SCATTER8(1),.JOB_DONE_EDGE_SELECT(1),.TIMEOUT_BITS(12)) dut(
 .clk(clk),.rst_n(rst_n),.frame_valid(frame_valid),.frame_ready(frame_ready),.frame_base(frame_base),
 .in_valid(iv),.in_ready(ir),.in_x(ix),.in_y(iy),.in_tag(itag),.out_valid(ov),.out_ready(ore),
 .p00(p00),.p10(p10),.p01(p01),.p11(p11),.fx(fx),.fy(fy),.out_tag(otag),
 .araddr(ca),.arlen(cl),.arvalid(cv),.arready(cr),.rdata(cd),.rvalid(crv),.rlast(crl),.rid(crid),
 .failed(failed),.fault(fault),.hits(hits),.misses(misses),.completed_queries(queries));
ddr_read_arbiter #(.TIMEOUT_BITS(12)) arb(.clk(clk),.rst_n(rst_n),.display_urgent(1'b0),
 .c0_araddr(28'd0),.c0_arlen(4'd15),.c0_arvalid(1'b0),.c0_arready(),.c0_rdata(),.c0_rvalid(),.c0_rlast(),.c0_rid(),
 .c1_araddr(ca),.c1_arlen(cl),.c1_arvalid(cv),.c1_arready(cr),.c1_rdata(cd),.c1_rvalid(crv),.c1_rlast(crl),.c1_rid(crid),
 .araddr(araddr),.arlen(arlen),.arvalid(arvalid),.arready(arready),.rdata(rdata),.rvalid(rv),.rlast(rl),.rid(rid),
 .failed(arbfailed),.fault(arbfault),.busy(arbbusy),.bursts0(b0),.bursts1(b1));
`ifdef ONE_PENDING_MODEL
 ddr_shared_pressure_model #(.R_LATENCY(32)) model(
`else
 ddr_ordered_two_credit_model #(.R_LATENCY(32),.REF_PERIOD(113),.REF_CYCLES(7),.REF_PHASE(23),.STOP_PERIOD(251),.STOP_CYCLES(9),.STOP_PHASE(71)) model(
`endif
 .clk(clk),.rst_n(rst_n),.araddr(araddr),.arlen(arlen),.arvalid(arvalid),.arready(arready),
 .awaddr(28'd0),.awlen(4'd0),.awvalid(1'b0),.awready(unused_awready),.wdata(256'd0),.wstrb(32'd0),.wready(unused_wready),.wlast(unused_wlast),
 .rdata(rdata),.rvalid(rv),.rlast(rl),.rid(rid),.mem_raddr(memaddr),.mem_rdata(memdata),.mem_waddr(unused_memwa),
 .mem_we(unused_memwe),.mem_wdata(unused_memwd),.mem_wstrb(unused_memws),.refresh_active(unused_ref),.stop_active(unused_stop),
 .tick(tick),.read_commands(nar),.write_commands(naw),.read_beats(nr),.write_beats(nw),.refresh_cycles(nref),.stop_cycles(nstop),.turn_wait_cycles(nturn));
function automatic [15:0] raw(input integer index);reg [31:0] z;begin z=index*109+32'h529b;z=z^(index>>3)^((index>>10)*32'h1f2d);raw=z[15:0];end endfunction
function automatic [23:0] expand(input [15:0] p);expand={p[15:11],p[15:13],p[10:5],p[10:9],p[4:0],p[4:2]};endfunction
function automatic [23:0] golden(input integer x,y,input [27:0] base);begin
 if(x<0||x>=1920||y<0||y>=1080)golden=0;else golden=expand(raw(base*2+y*1920+x));
end endfunction
genvar g;generate for(g=0;g<16;g=g+1)begin assign memdata[g*16+:16]=raw(memaddr*2+g);end endgenerate
integer sent=0,got=0,base_index=0,peak=0,mask_merge=0,hot_run=0,hot_peak=0;reg hot=0;
integer ex[0:1023],ey[0:1023];reg [7:0] efx[0:1023],efy[0:1023];reg [27:0] eb[0:1023];
reg held=0;reg [31:0] saved;
always @(posedge clk)if(rst_n)begin
 if(failed||arbfailed)$fatal(1,"cache/arb fault %h %h",fault,arbfault);
 if(held&&(!cv||{cl,ca}!==saved))$fatal(1,"cache AR hold");held=cv&&!cr;saved={cl,ca};
 if(frame_ready&&(dut.inflight_count!=0||dut.store_fill_busy||dut.job_hold||arbbusy))$fatal(1,"frame ready before both leases/DDR drain");
 if(dut.inflight_count>peak)peak=dut.inflight_count;
 if(dut.fill_accept&&dut.fill_done_good)mask_merge=mask_merge+1;
 if(dut.inflight_count==2&&dut.owner_line[0]==dut.owner_line[1])$fatal(1,"duplicate cache lease owner");
 if(iv&&ir)begin
  if(itag!==sent)$fatal(1,"input tag monotonic");
  ex[sent]=$signed(ix)>>>8;ey[sent]=$signed(iy)>>>8;efx[sent]=ix[7:0];efy[sent]=iy[7:0];eb[sent]=frame_base;sent=sent+1;
 end
 if(ov&&ore)begin
  if(otag!==got||p00!==golden(ex[got],ey[got],eb[got])||p10!==golden(ex[got]+1,ey[got],eb[got])||
   p01!==golden(ex[got],ey[got]+1,eb[got])||p11!==golden(ex[got]+1,ey[got]+1,eb[got])||fx!==efx[got]||fy!==efy[got])
    $fatal(1,"independent cache pixel/tag/fraction mismatch tag=%0d expected=%0d got00=%h expected00=%h",otag,got,p00,golden(ex[got],ey[got],eb[got]));
  got=got+1;
 end
 if(hot&&ov&&ore)begin hot_run=hot_run+1;if(hot_run>hot_peak)hot_peak=hot_run;end else hot_run=0;
end

task load_frame(input [27:0] base);begin
 @(negedge clk);frame_base=base;frame_valid=1;
 @(posedge clk);while(!frame_ready)@(posedge clk);
 @(negedge clk);frame_valid=0;
end endtask

task push_query(input integer x,y,frac);begin
 @(negedge clk);ix=x*256+(frac&255);iy=y*256+((frac*3)&255);itag=sent;iv=1;
 @(posedge clk);while(!ir)@(posedge clk);
end endtask

task drain;begin
 @(negedge clk);iv=0;
 while(got!=sent||!frame_ready)@(negedge clk);
 repeat(4)@(negedge clk);
end endtask
integer i,frame_start_got;
initial begin
 repeat(5)@(negedge clk);rst_n=1;load_frame(0);
 for(i=0;i<64;i=i+1)push_query(i,0,i);drain();
 hot=1;for(i=0;i<96;i=i+1)push_query(i,0,i+4);drain();hot=0;
 if(hot_peak<64)$fatal(1,"hot II1 not achieved peak=%0d",hot_peak);
 // A/B/A aliases both parity owners. Every generation is checked from source.
 for(i=0;i<48;i=i+1)push_query(i,64,i+1);drain();
 for(i=0;i<48;i=i+1)push_query(i,0,i+2);drain();
 // While a third cold pair is in flight, offer a frame boundary. Base remains
 // old until the entire old input/result/refill domain reaches quiescence.
 for(i=0;i<32;i=i+1)push_query(i,128,i+3);
 @(negedge clk);iv=0;frame_valid=1;
 if(frame_ready)$fatal(1,"cold work unexpectedly already quiescent");
 while(!frame_ready)@(negedge clk);
 frame_base=28'h100000;
 @(posedge clk);if(!frame_ready)$fatal(1,"ready withdrew at accepted frame");
 @(negedge clk);frame_valid=0;
 for(i=0;i<40;i=i+1)push_query(i,0,i+5);drain();
 if(sent!=328||got!=328||peak!=2||nr!=nar*8||b1!=nar||arbbusy)$fatal(1,"cache final conservation sent=%0d got=%0d peak=%0d",sent,got,peak);
 $display("PASS_DUAL_CACHE independent_queries=%0d hot_II1_run=%0d peak_leases=%0d simultaneous_completion_allocation=%0d AR=%0d R=%0d source_frames=2",got,hot_peak,peak,mask_merge,nar,nr);
 $finish;
end
initial begin #1000000;$fatal(1,"cache TB watchdog");end
endmodule
