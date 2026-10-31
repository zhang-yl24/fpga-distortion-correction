`timescale 1ns/1ps
// Observer reset is released into an independently running raster. No force,
// no changing DUT parameters/state, and no stub of the CDC mailbox.
module tb_trained_enable_phase;
  reg ref_clk=0,pix_clk=0,rst_n=0,polarity=0;
  always #18.5 ref_clk=~ref_clk;
  initial begin #1.777;forever #7 pix_clk=~pix_clk;end
  integer x=0,y=0;
  reg vs=0,hs=0,de=0;
  always @(negedge pix_clk)begin
    vs=(y<1)^polarity;hs=(x<2)^polarity;
    de=(y>=2 && y<5 && x>=4 && x<12);
    if(x==15)begin x=0;if(y==7)y=0;else y=y+1;end else x=x+1;
  end
  wire known,vi,hi,qualified,failed;
  wire [7:0] fault;
  wire [31:0] good,bad,edges;
  wire [15:0] width,height;
  hdmi1080_input_status_trained #(.WIDTH(8),.HEIGHT(3),.HTOTAL(16),.VTOTAL(8),
      .ACTIVITY_REF_CYCLES(50),.PCLK_WINDOW_MIN(120),.PCLK_WINDOW_MAX(145)) dut(
    .ref_clk(ref_clk),.pix_clk(pix_clk),.rst_n(rst_n),.pix_vs(vs),.pix_hs(hs),.pix_de(de),
    .normalized_vs(),.qualified(qualified),.failed(failed),.fault(fault),
    .polarity_known_ref(known),.vs_inactive_ref(vi),.hs_inactive_ref(hi),
    .good_frames(good),.bad_frames(bad),.pclk_edges_per_window(edges),
    .last_pixels_per_line(width),.last_lines(height));
  integer epoch=0,elapsed=0,cases=0,applications=0,p_starts=0,r_starts=0;
  reg seen_p=0,seen_r=0;
  always @(posedge pix_clk)begin
    #0.001;
    if(!rst_n)seen_p=0;
    else if(dut.geometry.p_reset[1])begin
      if(seen_p && !dut.geometry.p_run)$fatal(1,"monotonic source enable dropped");
      if(dut.geometry.p_run && !seen_p)begin seen_p=1;p_starts=p_starts+1;end
    end
  end
  always @(posedge ref_clk)begin
    #0.001;
    if(!rst_n)seen_r=0;
    else if(dut.geometry.r_reset[1])begin
      if(seen_r && !dut.geometry.r_run)$fatal(1,"monotonic reference enable dropped");
      if(dut.geometry.r_run && !seen_r)begin
        if(!dut.geometry.p_run || !dut.geometry.source_running_sync[1])$fatal(1,"reference ran before source enabled");
        seen_r=1;r_starts=r_starts+1;
      end
      if(dut.geometry.r_run && dut.geometry.snapshot_apply)applications=applications+1;
    end
  end
  initial begin
    for(epoch=0;epoch<8;epoch=epoch+1)begin
      @(negedge ref_clk);rst_n=0;polarity=epoch%2;
      repeat(12)@(negedge ref_clk);
      while(x!=(epoch*2))@(negedge pix_clk);
      #3;rst_n=1;
      elapsed=0;
      while(!qualified && elapsed<40000)begin @(negedge ref_clk);elapsed=elapsed+1;end
      if(!qualified || failed || fault || !seen_p || !seen_r || good<2 || bad || width!=8 || height!=3 || vi!==polarity || hi!==polarity)
        $fatal(1,"phase%0d did not qualify known%0d prun%0d rrun%0d good%0d bad%0d fault%h width%0d height%0d",epoch,known,dut.geometry.p_run,dut.geometry.r_run,good,bad,fault,width,height);
      $display("TRAINED_ENABLE_PHASE_PASS epoch=%0d reset_release_x=%0d polarity=%0d ref_cycles=%0d good=%0d bad=%0d width=%0d height=%0d snapshots=%0d",epoch,epoch*2,polarity,elapsed,good,bad,width,height,applications);
      cases=cases+1;
    end
    if(cases!=8 || p_starts!=8 || r_starts!=8 || applications<8)$fatal(1,"phase sweep coverage missing");
    $display("TRAINED_ENABLE_PHASE_SUMMARY cases=%0d source_starts=%0d reference_starts=%0d snapshots=%0d",cases,p_starts,r_starts,applications);
    $display("TRAINED_ENABLE_PHASE_SWEEP_PASS");$finish;
  end
endmodule
