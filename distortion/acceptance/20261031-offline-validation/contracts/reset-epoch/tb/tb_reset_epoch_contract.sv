`timescale 1ns/1ps
module tb_reset_epoch_contract;
 reg ref_clk=0,pclk=0,reset_n=1,ready_request=0,readiness_ref=0;
 integer x=0,y=0,epoch=0,case_id=0;
 wire vs=(y==6),href=(y<4 && x>=1 && x<=8);
 always @(posedge pclk)begin
  if(x==15)begin x<=0;if(y==7)y<=0;else y<=y+1;end
  else x<=x+1;
 end
 // A reference-clock REGISTER with common asynchronous assertion, matching
 // the relevant top-level precondition, not a model of the full I2C delay.
 always @(posedge ref_clk or negedge reset_n)
  if(!reset_n)readiness_ref<=0;else readiness_ref<=ready_request;
 wire [2:0] lr,pr,rr,runp,runr,req,ack,seen,settle,apply,auth,rpermit,ppermit,blocked;
 wire [1:0] rs[0:2],as[0:2];
 wire [104:0] held[0:2],bundle[0:2];
 wire [31:0] source_good[0:2],published_good[0:2];
 integer errors[0:2],applies[0:2],captures[0:2],bundle_changes[0:2];
 integer uncommitted[0:2];
 integer out;
 genvar g;
 generate for(g=0;g<3;g=g+1)begin: probes
  reset_contract_probe #(.KIND(g)) probe(
   .ref_clk(ref_clk),.pclk(pclk),.reset_n(reset_n),.readiness_ref(readiness_ref),
   .vs(vs),.href(href),.local_reset_n(lr[g]),.p_release(pr[g]),.r_release(rr[g]),
   .p_run(runp[g]),.r_run(runr[g]),.req(req[g]),.ack(ack[g]),.ack_seen(seen[g]),
   .settle(settle[g]),.apply(apply[g]),.authorize(auth[g]),.request_sync(rs[g]),
   .ack_sync(as[g]),.held(held[g]),.reference_bundle(bundle[g]),
   .source_good(source_good[g]),.published_good(published_good[g]),
   .ref_permit(rpermit[g]),.pixel_permit(ppermit[g]),.blocked(blocked[g]));
  reg pclean=0,rclean=0;
  integer p_edges=0,r_edges=0,held_epoch=-1,armed_epoch=-1;
  reg [104:0] armed_bundle;
  reg armed_ack;
  reg [104:0] expected_capture,expected_hold;
  reg [31:0] expected_publication;
  task problem(input string code);
   begin
    errors[g]=errors[g]+1;
    $fdisplay(out,"ERROR,%0d,%0d,%0d,%0t,%0s",case_id,g,epoch,$time,code);
    $fflush(out);
    if(g<2)$fatal(1,"contract error case=%0d kind=%0d code=%0s",case_id,g,code);
   end
  endtask
  initial begin errors[g]=0;applies[g]=0;captures[g]=0;bundle_changes[g]=0;uncommitted[g]=0;end
  always @(negedge reset_n)begin pclean=0;rclean=0;held_epoch=-1;armed_epoch=-1;end
  always @(negedge lr[g])begin p_edges=0;r_edges=0;end
  always @(posedge pclk)begin
   if(pr[g] && p_edges<2)problem("P_RELEASE_BEFORE_TWO_EDGES");
   if(runp[g] && p_edges<2)problem("P_USE_BEFORE_THIRD_EDGE");
   if(!lr[g])p_edges=0;else p_edges=p_edges+1;
   if(!runp[g])begin
    pclean=1;held_epoch=-1;
    #0.001;
    if(held[g]!==105'b0 || ack[g]!==1'b0 || rs[g]!==2'b0 || source_good[g]!==32'b0)
     problem("P_BUSINESS_NOT_CLEARED");
   end else if(rs[g][1]!=ack[g])begin
    if(!rclean)begin uncommitted[g]=uncommitted[g]+1;problem("SOURCE_BEFORE_REF_CLEAN");end
    captures[g]=captures[g]+1;held_epoch=epoch;
   end else begin
    expected_hold=held[g];#0.001;
    if(held[g]!==expected_hold)problem("HELD_CHANGED_WITHOUT_REQUEST");
   end
  end
  always @(posedge ref_clk)begin
   if(rr[g] && r_edges<2)problem("R_RELEASE_BEFORE_TWO_EDGES");
   if(runr[g] && r_edges<2)problem("R_USE_BEFORE_THIRD_EDGE");
   if(!lr[g])r_edges=0;else r_edges=r_edges+1;
   if(!runr[g])begin
    rclean=1;armed_epoch=-1;
    #0.001;
    if(req[g]!==1'b0 || as[g]!==2'b0 || seen[g]!==1'b0 || settle[g]!==1'b0 ||
       apply[g]!==1'b0 || bundle[g]!==105'b0 || published_good[g]!==32'b0)
     problem("R_BUSINESS_NOT_CLEARED");
   end else begin
    if(apply[g])begin
     if(!pclean || !rclean || armed_epoch!=epoch)problem("OLD_EPOCH_APPLY");
     applies[g]=applies[g]+1;expected_publication=bundle[g][104:73];
     $fdisplay(out,"APPLY,%0d,%0d,%0d,%0t,%0d",case_id,g,epoch,$time,expected_publication);$fflush(out);
     #0.001;if(published_good[g]!==expected_publication)problem("PUBLISHED_NOT_CAPTURED_BUNDLE");
    end else if(settle[g])begin
     if(!pclean || !rclean || armed_epoch!=epoch)problem("OLD_EPOCH_CAPTURE");
     if(held[g]!==armed_bundle || as[g][1]!==armed_ack)begin
      bundle_changes[g]=bundle_changes[g]+1;problem("BUNDLE_CHANGED_AFTER_ACK_DETECTION");
     end
     expected_capture=held[g];#0.001;
     if(bundle[g]!==expected_capture)problem("CAPTURE_NOT_AT_SETTLE");
    end else if(as[g][1]!=seen[g])begin
     armed_bundle=held[g];armed_ack=as[g][1];armed_epoch=held_epoch;
    end
   end
  end
 end endgenerate

 task tick(input integer mode);
  begin
   #5;if(mode==1 || mode==3)pclk=1;if(mode==2 || mode==3)ref_clk=1;
   #2;pclk=0;ref_clk=0;#3;
  end
 endtask
 task normal_round;
  begin tick(1);tick(1);tick(1);tick(2);end
 endtask
 task mark(input [255:0] label);
  begin $display("CONTRACT_PROGRESS case=%0d epoch=%0d %0s",case_id,epoch,label);
   $fdisplay(out,"MARK,%0d,-1,%0d,%0t,%0s",case_id,epoch,$time,label);$fflush(out);end
 endtask
 task common_reset;
  begin
   epoch=epoch+1;ready_request=0;
   #0.001;reset_n=0;#0.002;
   if(pr!==3'b0 || rr!==3'b0 || rpermit[1]!==0 || ppermit[1]!==0)
    $fatal(1,"asynchronous common assertion requires no clock");
   #0.004;reset_n=1;
  end
 endtask
 task recover_and_publish;
  integer a,b,n;
  begin
   a=applies[0];b=applies[1];ready_request=1;n=0;
   while((applies[0]==a || applies[1]==b) && n<30050)begin normal_round();n=n+1;end
   if(applies[0]==a || applies[1]==b)$fatal(1,"recovery made no fresh publication");
   repeat(4)normal_round();
   if(published_good[0]==0 || published_good[1]==0 || !auth[0] || !auth[1])
    $fatal(1,"recovery did not authorize real fresh synthetic geometry");
   mark("FRESH_EPOCH_PUBLISHED");
  end
 endtask
 integer n,j;
 initial begin
  out=$fopen("contract.csv","w");if(!out)$fatal(1,"cannot open contract.csv");
  $fdisplay(out,"event,case,kind,epoch,time,value");$fflush(out);
  case_id=1;common_reset();ready_request=1;mark("MATURE_REAL_27000_TIMER");
  n=0;
  while(!(req[2]===1'b1 && ack[2]===1'b0 && runr[0] && runr[1]) && n<30050)
   begin normal_round();n=n+1;end
  if(n>=30050)$fatal(1,"negative witness precondition not reached");
  mark("OUTSTANDING_REQ_ONE");
  // Ref clock now stops. The common reset cannot clean synchronous ref
  // business state until it resumes. Baseline/guarded candidate must wait.
  case_id=2;common_reset();ready_request=1;
  n=0;while(ack[2]!==1'b1 && n<80)begin tick(1);n=n+1;end
  if(ack[2]!==1'b1)$fatal(1,"raw-release negative failed to respond to stale request");
  repeat(256)tick(1);
  if(ack[0]!==0 || ack[1]!==0 || runp[0] || runp[1])
   $fatal(1,"reference-stop reset let protected source run");
  mark("REF_STOP_PROTECTED");
  repeat(8)tick(2);
  if(settle[2]!==1'b1 || req[2]!==0)$fatal(1,"negative settle precondition missing");
  repeat(3)tick(1);tick(2);
  if(bundle_changes[2]<1 || uncommitted[2]<1)$fatal(1,"negative control was not rejected");
  mark("RAW_GUARD_REMOVAL_REJECTED");
  case_id=3;common_reset();recover_and_publish();
  // Stop PCLK, reset both domains asynchronously, then run ref alone.
  case_id=4;common_reset();ready_request=1;repeat(20)tick(2);
  if(pr!==3'b0 || auth[0] || auth[1])$fatal(1,"stopped pixel domain released");
  mark("PCLK_STOP_PROTECTED");recover_and_publish();
  // PCLK progresses while ref is stopped, without a reset: a held request
  // may be answered once, but its bundle cannot overwrite without new req.
  case_id=5;repeat(256)tick(1);mark("REF_RESUME_NO_RESET");
  recover_and_publish();
  // Ready loss is generated on a reference edge, never illegally changing
  // a reference register while its clock is stopped.
  case_id=6;ready_request=0;tick(2);
  if(auth[0] || auth[1])$fatal(1,"ready loss did not mask publication");
  ready_request=1;repeat(20)tick(2);repeat(64)tick(1);repeat(20)tick(2);
  if(!blocked[1] || rpermit[1] || runr[1] || auth[1])$fatal(1,"ready bounce rearmed candidate");
  mark("READY_BOUNCE_FAIL_CLOSED");
  case_id=7;common_reset();recover_and_publish();
  // Relative edge order and a short asynchronous pulse, including a
  // simultaneous pair of clock edges, exercise NBA reset-release ordering.
  case_id=8;
  for(j=0;j<3;j=j+1)begin
   common_reset();ready_request=1;
   repeat(j+1)tick(1);repeat(4-j)tick(2);tick(3);
   if(auth[0] || auth[1])$fatal(1,"fresh epoch authorized before new snapshot");
  end
  recover_and_publish();mark("ASYNC_PHASE_ORDERS_CHECKED");
  if(errors[0] || errors[1] || applies[0]<5 || applies[1]<5 || bundle_changes[2]<1)
   $fatal(1,"mandatory coverage missing");
  $fdisplay(out,"PASS,0,-1,%0d,%0t,baseline=%0d candidate=%0d negative=%0d",epoch,$time,applies[0],applies[1],bundle_changes[2]);
  $fflush(out);$fclose(out);
  $display("RESET_EPOCH_CONTRACT_PASS baseline=%0d candidate=%0d negative=%0d",applies[0],applies[1],bundle_changes[2]);
  $finish;
 end
 initial begin #20000000;$fatal(1,"20ms simulation watchdog");end
endmodule
