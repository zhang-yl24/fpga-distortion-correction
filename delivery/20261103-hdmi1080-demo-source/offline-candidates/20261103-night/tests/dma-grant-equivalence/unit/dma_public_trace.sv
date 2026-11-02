`timescale 1ps/1ps
// Independent passive second top: original stimulus/TB/oracle remain byte exact.
// Inputs and outputs are sampled pre-NBA and 1ps post-NBA on every sys edge.
`define B tb_dma_descriptor2
module dma_public_trace;
  integer trace_fd,cycle=0,checked=0,grants=0,reset_edges=0;
  initial begin
    trace_fd=$fopen("public_trace.csv","w");
    if(trace_fd==0)$fatal(1,"cannot open public trace");
    $fdisplay(trace_fd,"cycle,time_ps,sample,pix_clk,sys_clk,rst_n,enable,pix_vsync_active,pix_de,pix_rgb,source_writable,source_released,released_bank,source_valid,source_ready,source_bank,source_id,source_crc,source_pixels,capture_reserved,awaddr,awlen,awvalid,awready,wdata,wstrb,wready,wlast,write_active,failed,fault,accepted_frames,dropped_frames,overflow_frames,no_free_frames,last_drop_fault");
  end
  task automatic sample(input [8*4-1:0] stage_name);
    begin
      $fdisplay(trace_fd,"%0d,%0d,%0s,%h,%h,%h,%h,%h,%h,%06h,%h,%h,%h,%h,%h,%h,%08h,%08h,%08h,%h,%07h,%h,%h,%h,%064h,%08h,%h,%h,%h,%h,%02h,%08h,%08h,%08h,%08h,%02h",
        cycle,$time,stage_name,`B.pclk,`B.clk,`B.rst_n,`B.enable,`B.vs,`B.de,`B.rgb,
        `B.source_writable,`B.source_released,`B.released_bank,`B.source_valid,`B.source_ready,
        `B.source_bank,`B.source_id,`B.source_crc,`B.source_pixels,`B.capture_reserved,
        `B.awaddr,`B.awlen,`B.awvalid,`B.awready,`B.wdata,`B.wstrb,`B.wready,`B.wlast,
        `B.write_active,`B.failed,`B.fault,`B.accepted,`B.dropped,`B.overflow,`B.no_free,`B.last_drop_fault);
    end
  endtask
  always @(posedge `B.clk) begin
    cycle=cycle+1;
    // These evaluate the pre-edge values, before either DUT block updates.
    if(`B.rst_n) begin
      checked=checked+1;
      if(`B.dut.sys_reset !== `B.dut.capture.sys_reset)$fatal(1,"DMA/capture reset release differs pre-edge");
      if(`B.dut.active !== `B.dut.capture.grant_busy)$fatal(1,"active != capture.grant_busy pre-edge");
      if(`B.dut.grant_valid === 1'b1) begin
        grants=grants+1;
        if(`B.dut.grant_ready !== 1'b1)$fatal(1,"grant_valid does not imply grant_ready pre-edge");
      end
    end else reset_edges=reset_edges+1;
    sample("pre");
    #1;sample("post");
  end
  final begin
    $fflush(trace_fd);$fclose(trace_fd);
    $display("PAIR_INVARIANTS checked=%0d grants=%0d reset_edges=%0d",checked,grants,reset_edges);
  end
endmodule
`undef B
