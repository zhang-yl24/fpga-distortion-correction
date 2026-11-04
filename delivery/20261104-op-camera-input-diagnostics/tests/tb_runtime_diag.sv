`timescale 1ns/1ps
module tb_runtime_diag;
 reg clk=0;always #18.518519 clk=~clk;
 reg rst=0,released=0,qualified=1,failed=0,ready=1;
 reg [255:0] live=0;wire first_valid,follow_valid;wire [255:0] first,follow;wire [31:0] tick;wire wrapped;
 hdmi_input_runtime_snapshot #(.FOLLOWUP_REF_CYCLES(4)) dut(.ref_clk(clk),.rst_n(rst),
  .pipeline_released(released),.qualified(qualified),.input_failed(failed),.ready_all(ready),
  .live_tuple(live),.first_valid(first_valid),.follow_valid(follow_valid),.first_tuple(first),.follow_tuple(follow),
  .ref_uptime(tick),.uptime_wrapped(wrapped));
 integer checks=0;reg snapshot_done=0,wire_done=0,status_done=0;
 task step;begin @(posedge clk);#0.001;end endtask
 task reset_probe;begin @(negedge clk);rst=0;#0.001;
  if(first_valid || follow_valid || first!==0 || follow!==0)$fatal(1,"async snapshot reset");
  @(negedge clk);rst=1;released=0;qualified=1;failed=0;ready=1;end endtask
 initial begin
  #1;reset_probe();qualified=0;live=256'h11;repeat(3)step();
  if(first_valid)$fatal(1,"startup must not latch runtime failure");checks=checks+1;
  @(negedge clk);released=1;qualified=1;repeat(3)step();
  if(first_valid)$fatal(1,"healthy release falsely latches");checks=checks+1;
  @(negedge clk);qualified=0;live=256'h12345678;step();
  if(!first_valid || first!==256'h12345678 || follow_valid)$fatal(1,"first loss atomic edge");checks=checks+1;
  @(negedge clk);qualified=1;live=256'habcdef;repeat(3)begin step();if(follow_valid)$fatal(1,"follow early");end
  step();if(!follow_valid || follow!==256'habcdef || first!==256'h12345678)$fatal(1,"follow delay/first hold");checks=checks+1;
  @(negedge clk);qualified=0;failed=1;live=256'h777;repeat(5)step();
  if(first!==256'h12345678 || follow!==256'habcdef)$fatal(1,"later failure overwrites first");checks=checks+1;
  reset_probe();@(negedge clk);released=1;failed=1;live=256'hfa11;step();
  if(!first_valid || first!==256'hfa11)$fatal(1,"failed while qualified");checks=checks+1;
  reset_probe();@(negedge clk);released=1;ready=0;live=256'hbead;step();
  if(!first_valid || first!==256'hbead)$fatal(1,"ready loss while qualified");checks=checks+1;
  reset_probe();step();if(first_valid || follow_valid)$fatal(1,"new epoch stale tuple");checks=checks+1;
  $display("PASS_RUNTIME_SNAPSHOT cases=%0d first_hold follow_delay reset no_feedback",checks);snapshot_done=1;
 end
 reg uf=0,up=0,uw=0;reg [255:0] ufirst=0,ufollow=0,ulive=0;wire tx;
 hdmi_input_runtime_diag_uart #(.GAP_CLKS(20),.MAX_PACKETS(2),.CLOCK_HZ(27000000),.BAUD(2700000)) uart(
  .clk_27m(clk),.first_valid(uf),.follow_valid(up),.uptime_wrapped(uw),
  .first_tuple(ufirst),.follow_tuple(ufollow),.live_tuple(ulive),.telemetry_tx(tx));
 integer fd,j,k;reg [7:0] b;localparam real BIT_NS=370.37038;
 initial begin
  for(j=0;j<8;j=j+1)begin ulive[j*32+:32]=32'h1000+j;ufirst[j*32+:32]=32'ha000+j;ufollow[j*32+:32]=32'hb000+j;end
  fd=$fopen("runtime_uart.bin","wb");if(!fd)$fatal(1,"open UART capture");
  for(j=0;j<168;j=j+1)begin
   @(negedge tx);#(BIT_NS*1.5);b=0;
   for(k=0;k<8;k=k+1)begin b[k]=tx;#(BIT_NS);end
   if(tx!==1)$fatal(1,"UART stop bit");$fwrite(fd,"%c",b);
   if(j==10)begin uf=1;up=1;ulive={8{32'hcccccccc}};end
  end
  $fclose(fd);wire_done=1;$display("PASS_RUNTIME_UART_WIRE bytes=168 packets=2");
 end
 reg pclk=0,pclk_run=1;always begin #4;if(pclk_run)pclk=~pclk;end
 reg srst=0,vs=0,hs=0,de=0,wide_line=0;integer h=0,v=0;
 always @(negedge pclk)begin
  if(!srst)begin h=0;v=0;vs=0;hs=0;de=0;end
  else begin
   vs=(v==0);hs=(h<2);de=(v>=2 && v<6 && h>=4 && h<(wide_line ? 13:12));
   if(h==15)begin h=0;v=(v==7 ? 0:v+1);end else h=h+1;
  end
 end
 wire cq,cf,cfq,cff,rfq,rff,rq,rf;wire [7:0] cfc,rfc;wire [31:0] cg,cb,rg,rb,cp,rp,reason;
 hdmi1080_input_status #(.WIDTH(8),.HEIGHT(4),.HTOTAL(16),.VTOTAL(8),.ACTIVITY_REF_CYCLES(32),.PCLK_WINDOW_MIN(140),.PCLK_WINDOW_MAX(160)) observed(
  .ref_clk(clk),.pix_clk(pclk),.rst_n(srst),.pix_vs(vs),.pix_hs(hs),.pix_de(de),
  .qualified(cq),.failed(cf),.fault(cfc),.good_frames(cg),.bad_frames(cb),.pclk_edges_per_window(cp),
  .functional_qualified(cfq),.functional_failed(cff),.qualify_reason_ref_debug(reason));
 reference_hdmi1080_input_status #(.WIDTH(8),.HEIGHT(4),.HTOTAL(16),.VTOTAL(8),.ACTIVITY_REF_CYCLES(32),.PCLK_WINDOW_MIN(140),.PCLK_WINDOW_MAX(160)) original(
  .ref_clk(clk),.pix_clk(pclk),.rst_n(srst),.pix_vs(vs),.pix_hs(hs),.pix_de(de),
  .qualified(rq),.failed(rf),.fault(rfc),.good_frames(rg),.bad_frames(rb),.pclk_edges_per_window(rp),
  .functional_qualified(rfq),.functional_failed(rff));
 integer miter_edges=0;
 always @(posedge clk)begin #0.001;
  if(srst)begin
   if({cq,cf,cfc,cg,cb,cp,cfq,cff}!=={rq,rf,rfc,rg,rb,rp,rfq,rff})$fatal(1,"passive reason changes original control");
   miter_edges=miter_edges+1;
  end
 end
 initial begin
  repeat(5)step();@(negedge clk);srst=1;
  wait(cfq===1);step();if(reason[23:16]!==0 || reason[10:0]!==0)$fatal(1,"healthy reason contradiction");
  $display("PASS_INPUT_REASON healthy qualified=1 PCLK=%0d",cp);
  @(negedge pclk);wide_line=1;wait(cff===1);step();
  if(!reason[21] && !reason[23])$fatal(1,"bad geometry reason absent");
  $display("PASS_INPUT_REASON bad_geometry fault=%02h reason=%08h",cfc,reason);
  @(negedge clk);srst=0;wide_line=0;repeat(5)step();@(negedge clk);srst=1;
  wait(cfq===1);@(negedge pclk);pclk_run=0;
  wait(reason[20]===1);step();
  if(cfq!==0)$fatal(1,"bad rate retained qualification");
  $display("PASS_INPUT_REASON stopped_rate PCLK=%0d reason=%08h",cp,reason);
  repeat(27500)step();if(!reason[6])$fatal(1,"PCLK freshness reason absent");
  @(negedge clk);srst=0;repeat(3)step();if(cfq!==0)$fatal(1,"reset with stopped PCLK");
  status_done=1;$display("PASS_INPUT_REASON_MITER edges=%0d normal geometry rate stopped_reset",miter_edges);
 end
 initial begin wait(snapshot_done && wire_done && status_done);$display("RUNTIME_DIAGNOSTIC_SHORT_PASS");$finish;end
 initial begin #6000000;$fatal(1,"bounded diagnostic watchdog");end
endmodule
