`timescale 1ps/1ps
// Actual derived System/core reset routing and actual unchanged async FIFO.
// No vendor-IP model, PHY recovery, metastability or physical CDC claims.
module tb_reset_directed;
    reg core_clk=0,pix_in_clk=0,pix_out_clk=0,run_core=1;
    always #4000 if(run_core)core_clk=~core_clk;
    always #6734 pix_in_clk=~pix_in_clk;
    initial begin #1733;forever #6734 pix_out_clk=~pix_out_clk;end
    reg rst_n=0;
    hdmi1080_video_system #(.WIDTH(32),.HEIGHT(16),.HT(80),.VT(40),.HS(4),.VS(1),.X0(10),.Y0(3)) dut(
        .core_clk(core_clk),.pix_in_clk(pix_in_clk),.pix_out_clk(pix_out_clk),.rst_n(rst_n),
        .capture_admit(1'b0),.scan_enable(1'b0),.external_fault(1'b0),.external_fault_code(8'd0),
        .pix_in_vsync_active(1'b0),.pix_in_de(1'b0),.pix_in_rgb(24'd0),
        .cfg_out_cx(24'd0),.cfg_out_cy(24'd0),.cfg_src_cx(24'd0),.cfg_src_cy(24'd0),
        .cfg_src_fx(24'd4096),.cfg_src_fy(24'd4096),.cfg_inv_fx(32'd1),.cfg_inv_fy(32'd1),
        .cfg_k1(32'd0),.cfg_k2(32'd0),.cfg_k3(32'd0),.cfg_p1(32'd0),.cfg_p2(32'd0),
        .awready(1'b0),.arready(1'b0),.wready(1'b0),.wlast(1'b0),
        .rdata(256'd0),.rvalid(1'b0),.rlast(1'b0),.rid(4'd0));
    reg push=0,pop=0;reg [15:0] data=0;
    wire wr_ready,rd_ready,rd_valid;wire [15:0] rd_data;wire [2:0] wr_used,rd_available;
    video_async_fifo #(.DATA_BITS(16),.ADDR_BITS(2)) epoch_fifo(
        .wr_clk(core_clk),.rd_clk(pix_in_clk),.rst_n(rst_n),.wr_en(push),.wr_data(data),
        .wr_ready(wr_ready),.wr_used(wr_used),.rd_en(pop),.rd_ready(rd_ready),
        .rd_data(rd_data),.rd_valid(rd_valid),.rd_available(rd_available));
    integer phase_cases=0,k,f;
    task automatic assert_common;
        begin
            rst_n=0;push=0;pop=0;#1;
            if(dut.cr!==0 || dut.display_fifo.wr_reset_sync!==0 || dut.display_fifo.rd_reset_sync!==0 ||
               epoch_fifo.wr_reset_sync!==0 || epoch_fifo.rd_reset_sync!==0)
                $fatal(1,"common assertion did not reach all reset-release chains");
        end
    endtask
    task automatic check_release;
        begin
            @(posedge core_clk);#1;if(dut.cr!==0)$fatal(1,"core release before two edges");
            @(posedge core_clk);#1;if(dut.cr!==1)$fatal(1,"core did not release on second edge");
            repeat(6)@(negedge core_clk);
            if(dut.bank_core.rst_n!==dut.cr || dut.reader.rst_n!==dut.cr || dut.read_bus.rst_n!==dut.cr)
                $fatal(1,"core child raw asynchronous reset bypass");
            if(dut.bank_core.processing || dut.bank_core.pending || dut.bank_core.display_active ||
               dut.source_release || dut.result_publish || dut.read_busy || dut.write_busy)
                $fatal(1,"stale bank transaction after common epoch reset");
            repeat(5)@(negedge pix_in_clk);
            if(rd_ready || rd_valid || wr_used!=0 || rd_available!=0)$fatal(1,"old FIFO epoch survived reset");
        end
    endtask
    task automatic enqueue_old_epoch;
        begin
            @(negedge core_clk);data=16'h9000+phase_cases;push=1;
            @(negedge core_clk);push=0;
            repeat(6)@(negedge pix_in_clk);
            if(!rd_ready || rd_available!=1)$fatal(1,"pre-reset pending FIFO data not exercised");
        end
    endtask
    initial begin
        repeat(8)@(negedge core_clk);
        for(k=0;k<24;k=k+1)begin
            assert_common();repeat(6)@(negedge core_clk);
            if(k==22)begin #3999;end else if(k==23)begin #4001;end else begin #(137+k*157);end rst_n=1;check_release();enqueue_old_epoch();phase_cases=phase_cases+1;
        end
        // Safe common-epoch restart with core paused. This is not runtime
        // loss-of-clock recovery: no outstanding DDR transaction is modeled.
        assert_common();repeat(6)@(negedge core_clk);run_core=0;
        #1701;rst_n=1;repeat(8)@(negedge pix_in_clk);
        if(dut.cr || wr_ready || dut.source_release || dut.result_publish)$fatal(1,"stopped core incorrectly released");
        run_core=1;check_release();
        f=$fopen("summary.json","w");
        $fdisplay(f,"{\"passed\":true,\"phase_cases\":%0d,\"pending_fifo_epoch_cases\":%0d,\"stopped_core_release_cases\":1,\"physical_metastability_or_phy_verified\":false,\"runtime_clock_loss_recovery_verified\":false}",phase_cases,phase_cases);
        $fclose(f);$display("PASS reset directed: 24 asynchronous phases, local two-edge release, common FIFO epoch discard, core stopped before release");$finish;
    end
    initial begin #20000000;$fatal(1,"reset directed cycle/time budget exceeded");end
endmodule
