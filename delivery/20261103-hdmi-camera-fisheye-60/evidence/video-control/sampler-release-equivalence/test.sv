`timescale 1ps/1ps
module tb_sampler_release_equivalence;
 reg pclk=0,rst_n=1,raw_vs=0,raw_hs=0,raw_de=0;reg[23:0]raw_rgb=0;
 wire[5:0]ov,nv,ova,nva,oda,nda,ovs,nvs,ohs,nhs,ode,nde;
 wire[23:0]orgb[0:5],nrgb[0:5];
 genvar i;generate for(i=0;i<6;i=i+1)begin:polarity
  localparam VP=i<4?i/2:(i==4?2:1),DP=i<4?i%2:(i==4?1:2);
  hdmi_camera_pixel_sampler_old #(.VS_ACTIVE_LEVEL(VP),.DE_ACTIVE_LEVEL(DP)) old_sampler(
   .pclk(pclk),.rst_n(rst_n),.raw_vs(raw_vs),.raw_hs(raw_hs),.raw_de(raw_de),.raw_rgb(raw_rgb),
   .sampled_vs(ovs[i]),.sampled_hs(ohs[i]),.sampled_de(ode[i]),.sampled_rgb(orgb[i]),.sampled_valid(ov[i]),.vs_active(ova[i]),.de_active(oda[i]));
  hdmi_camera_pixel_sampler_new #(.VS_ACTIVE_LEVEL(VP),.DE_ACTIVE_LEVEL(DP)) new_sampler(
   .pclk(pclk),.rst_n(rst_n),.raw_vs(raw_vs),.raw_hs(raw_hs),.raw_de(raw_de),.raw_rgb(raw_rgb),
   .sampled_vs(nvs[i]),.sampled_hs(nhs[i]),.sampled_de(nde[i]),.sampled_rgb(nrgb[i]),.sampled_valid(nv[i]),.vs_active(nva[i]),.de_active(nda[i]));
 end endgenerate
 // Independent numeric reference: valid starts on release edge 3; data
 // first captures on that same edge. Reset assertion does not clear data
 // without a clock, matching the source interface's synchronous data clear.
 integer edges_since_reset=0;reg[26:0]reference_data;
 always @(posedge pclk or negedge rst_n)
  if(!rst_n)edges_since_reset<=0;else if(edges_since_reset<3)edges_since_reset<=edges_since_reset+1;
 always @(posedge pclk)
  if(edges_since_reset<2)reference_data<=0;else reference_data<={raw_vs,raw_hs,raw_de,raw_rgb};
 reg[1:0]quant_reset=0;
 always @(posedge pclk or negedge rst_n)
  if(!rst_n)quant_reset<=0;else quant_reset<={quant_reset[0],1'b1};
 wire qov,qnv,qovs,qnvs,qode,qnde;wire[23:0]qorgb,qnrgb;
 hdmi_camera_rgb565_quantizer qo(.clk(pclk),.rst_n(quant_reset[1]),.in_valid(ov[3]),.in_vs(ova[3]),.in_de(oda[3]),.in_rgb(orgb[3]),.out_valid(qov),.out_vs(qovs),.out_de(qode),.out_rgb(qorgb));
 hdmi_camera_rgb565_quantizer qn(.clk(pclk),.rst_n(quant_reset[1]),.in_valid(nv[3]),.in_vs(nva[3]),.in_de(nda[3]),.in_rgb(nrgb[3]),.out_valid(qnv),.out_vs(qnvs),.out_de(qnde),.out_rgb(qnrgb));
 reg ohist=0,nhist=0,oprev=0,nprev=0;integer oedges=0,nedges=0,obaselines=0,nbaselines=0;
 always @(posedge pclk)begin
  if(!quant_reset[1])begin ohist<=0;nhist<=0;oprev<=0;nprev<=0;end
  else begin
   if(ov[3])begin if(!ohist)obaselines=obaselines+1;else if(oprev!=ovs[3])oedges=oedges+1;oprev<=ovs[3];ohist<=1;end
   if(nv[3])begin if(!nhist)nbaselines=nbaselines+1;else if(nprev!=nvs[3])nedges=nedges+1;nprev<=nvs[3];nhist<=1;end
  end
 end
 integer checks=0,clock_edges=0,reset_assertions=0,stop_low=0,stop_high=0,coincident_assert=0,coincident_release=0;
 reg started=0;integer j;reg[31:0]random_state=32'h426217bd;
 always @(posedge pclk)clock_edges=clock_edges+1;
 always @(negedge rst_n)reset_assertions=reset_assertions+1;
 task check;
  integer k;
  begin if(started)begin
   for(k=0;k<6;k=k+1)begin
    if({ov[k],ova[k],oda[k],ovs[k],ohs[k],ode[k],orgb[k]}!=={nv[k],nva[k],nda[k],nvs[k],nhs[k],nde[k],nrgb[k]})
     $fatal(1,"old/new mismatch at %0t polarity %0d",$time,k);
    if(ov[k]!== (edges_since_reset==3) || {ovs[k],ohs[k],ode[k],orgb[k]}!==reference_data)
     $fatal(1,"independent reference mismatch t=%0t edge=%0d valid=%b olddata=%h refdata=%h oldreset=%b newreset=%b",$time,edges_since_reset,ov[k],{ovs[k],ohs[k],ode[k],orgb[k]},reference_data,polarity[0].old_sampler.p_reset,polarity[0].new_sampler.p_reset);
   end
   if({qov,qovs,qode,qorgb}!=={qnv,qnvs,qnde,qnrgb})$fatal(1,"quantizer latency/data mismatch");
   if(oedges!=nedges || obaselines!=nbaselines)$fatal(1,"consumer edge/history mismatch");
   if(!rst_n && (ov!=0 || nv!=0 || ova!=0 || nva!=0 || oda!=0 || nda!=0))$fatal(1,"asynchronous valid mask failed");
   checks=checks+1;
  end end
 endtask
 always @(pclk or rst_n or raw_vs or raw_hs or raw_de or raw_rgb)begin #1;check();end
 task tick;
  begin pclk=0;#7;raw_rgb=raw_rgb+24'h72391;raw_vs=!raw_vs;raw_de=!raw_de;#3;pclk=1;#11;check();pclk=0;#9;end
 endtask
 task stopped_reset(input integer high_level);
  integer m;reg[26:0]held;
  begin
   repeat(6)tick();if(high_level)begin pclk=1;#5;stop_high=stop_high+1;end else stop_low=stop_low+1;
   held={ovs[3],ohs[3],ode[3],orgb[3]};#3;rst_n=0;#5;
   if(ov!=0 || nv!=0 || {ovs[3],ohs[3],ode[3],orgb[3]}!==held)$fatal(1,"stopped-clock asynchronous mask/data retention mismatch");
   for(m=0;m<8;m=m+1)begin #7;raw_rgb=raw_rgb^24'hfaceda;raw_vs=!raw_vs;rst_n=!rst_n;end
   #3;rst_n=1;#19;
   if(ov!=0 || nv!=0 || {ovs[3],ohs[3],ode[3],orgb[3]}!==held)$fatal(1,"stopped release invented a sample");
   repeat(4)tick();
  end
 endtask
 initial begin
  #2;started=1;check();#3;rst_n=0;#13;rst_n=1;
  repeat(4)tick();stopped_reset(0);stopped_reset(1);
  // Reset during each prefix of the 3-edge release and during active data.
  for(j=0;j<5;j=j+1)begin rst_n=0;#9;rst_n=1;repeat(j)tick();#2;rst_n=0;#5;rst_n=1;repeat(4)tick();end
  // Coincident events share one simulation time; compare settled NBA state.
  pclk=0;#5;rst_n=0;pclk=1;coincident_assert=coincident_assert+1;#9;
  pclk=0;#5;rst_n=1;pclk=1;coincident_release=coincident_release+1;#9;repeat(5)tick();
  for(j=0;j<30000;j=j+1)begin
   random_state=random_state^(random_state<<13);random_state=random_state^(random_state>>17);random_state=random_state^(random_state<<5);
   #(2+random_state[4:0]);raw_rgb=random_state[23:0];raw_vs=random_state[24];raw_hs=random_state[25];raw_de=random_state[26];
   case(random_state[29:27])
    0:rst_n=0;
    1:rst_n=1;
    2:begin pclk=0;#2;rst_n=0;pclk=1;coincident_assert=coincident_assert+1;end
    3:begin pclk=0;#2;rst_n=1;pclk=1;coincident_release=coincident_release+1;end
    default:pclk=!pclk;
   endcase
  end
  #5;rst_n=1;repeat(12)tick();#3;check();
  if(checks<30000 || clock_edges<10000 || reset_assertions<2000 || oedges<100 || obaselines<100)$fatal(1,"equivalence coverage insufficient");
  begin integer f;f=$fopen("coverage.json","w");
   $fdisplay(f,"{\"passed\":true,\"settled_checks\":%0d,\"polarity_variants\":6,\"pclk_edges\":%0d,\"reset_assertions\":%0d,\"stopped_low\":%0d,\"stopped_high\":%0d,\"coincident_assert\":%0d,\"coincident_release\":%0d,\"consumer_baselines\":%0d,\"consumer_vs_edges\":%0d,\"quantizer_compared\":true,\"first_valid_edge\":3}",checks,clock_edges,reset_assertions,stop_low,stop_high,coincident_assert,coincident_release,obaselines,oedges);$fclose(f);end
  $display("PASS SAMPLER RELEASE EQUIVALENCE checks=%0d posedges=%0d resets=%0d polarities=6 consumer_edges=%0d",checks,clock_edges,reset_assertions,oedges);$finish;
 end
endmodule
