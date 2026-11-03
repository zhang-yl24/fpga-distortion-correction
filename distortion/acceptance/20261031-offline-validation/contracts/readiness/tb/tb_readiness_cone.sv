`timescale 1ns/1ps
module tb_readiness_cone;
 reg ref_clk=0,cfg_clk=0,pclk=0,reset_n=1;
 reg power_done=0,configuration_done=0,rx_finish=0,fault_event=0,hold_meta=0;
 wire [3:0] ready,ref_permit,pixel_permit,blocked;
 wire [14:0] debug_state[0:3];
 integer phase[0:3],violations[0:3],highs[0:3],drops[0:3];
 integer i,out;
 genvar g;
 generate for(g=0;g<4;g=g+1)begin: models
  readiness_cone_projection #(.MODE(g)) c(.ref_clk(ref_clk),.cfg_clk(cfg_clk),
   .reset_n(reset_n),.power_done(power_done),.configuration_done(configuration_done),
   .rx_finish(rx_finish),.fault_event(fault_event),.hold_meta(hold_meta),
   .readiness(ready[g]),.debug_state(debug_state[g]));
  observer_epoch_guard_candidate guard(.ref_clk(ref_clk),.pclk(pclk),
   .reset_n(reset_n),.readiness_ref(ready[g]),.ref_permit(ref_permit[g]),
   .pixel_permit(pixel_permit[g]),.blocked(blocked[g]));
 end endgenerate
 task inspect;
  integer k;
  begin
   for(k=0;k<4;k=k+1)begin
    if(!reset_n)phase[k]=0;
    else if(ready[k])begin
     highs[k]=highs[k]+1;
     if(phase[k]==2)begin violations[k]=violations[k]+1;phase[k]=3;end
     else if(phase[k]!=3)phase[k]=1;
    end else if(phase[k]==1)begin drops[k]=drops[k]+1;phase[k]=2;end
    if(k<3 && (violations[k]!=0 || (ready[k] && blocked[k])))
     $fatal(1,"source-cone property failed mode=%0d",k);
    $fdisplay(out,"%0t,%0d,%0d,%0d,%0d,%0d",$time,k,reset_n,ready[k],blocked[k],phase[k]);
   end
   $fflush(out);
  end
 endtask
 task tick(input integer mode);
  begin
   #5;if(mode==1 || mode==3)ref_clk=1;if(mode==2 || mode==3)cfg_clk=1;
   #1;inspect();#1;ref_clk=0;cfg_clk=0;#3;
  end
 endtask
 initial begin
  out=$fopen("readiness.csv","w");if(!out)$fatal(1,"open readiness.csv");
  $fdisplay(out,"time,mode,reset_n,ready,blocked,phase");
  for(i=0;i<4;i=i+1)begin phase[i]=0;violations[i]=0;highs[i]=0;drops[i]=0;end
  #1;reset_n=0;#1;inspect();
  `include "tb/witness.vh"
  if(violations[3]<1)$fatal(1,"checker did not reject double-nonsticky mutant");
  for(i=0;i<3;i=i+1)if(highs[i]==0 || drops[i]==0)$fatal(1,"vacuous replay mode%0d",i);
  // With both clocks stopped common reset still masks stale RX completion.
  reset_n=0;#1;inspect();
  if(ready!==0 || blocked!==0)$fatal(1,"asynchronous common invalidation failed");
  reset_n=1;#1;inspect();power_done=1;configuration_done=1;fault_event=0;rx_finish=1;hold_meta=0;
  repeat(10)tick(1); // cfg stopped: no fabricated RX initialization.
  if(ready!==0)$fatal(1,"cfg-stop released readiness without cfg work");
  repeat(12)tick(2); // ref stopped: reference completion cannot advance.
  if(ready!==0)$fatal(1,"ref-stop advanced reference completion");
  repeat(8)tick(1);
  if(ready!==4'b1111)$fatal(1,"new common epoch did not restore completion");
  repeat(3)begin #2;pclk=1;#2;pclk=0;end
  if(blocked!==0 || ref_permit!==4'b1111 || pixel_permit!==4'b1111)
   $fatal(1,"guard rejects healthy readiness in new epoch");
  $fdisplay(out,"PASS");$fflush(out);$fclose(out);
  $display("READINESS_CONE_REPLAY_PASS baseline_and_single_sticky_safe double_nonsticky_rejected");$finish;
 end
 initial begin #100000;$fatal(1,"100us watchdog");end
endmodule
