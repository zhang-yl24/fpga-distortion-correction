`timescale 1ps/1ps
// Actual checked board top; legacy opaque CDC stubs for PLL/DDR/status/system.
// The additional checked-wrapper stub drives status assumptions only. Actual
// wire-level driver/sequencer behavior is covered by a separate E2E regression.
module tb_board1080_checked_control;
    reg clk_27m=0,reset_n=0;
    integer phase=0,delay_ps,ticks=0;
    initial forever begin
        phase=phase+500000;delay_ps=phase/27;phase=phase%27;
        #(delay_ps)clk_27m=~clk_27m;
    end
    wire pix_clk,hs_out,vs_out,de_out,rstn_out;
    wire [7:0] r_out,g_out,b_out,led;tri1 hd_scl,hd_sda;
    wire mem_rst_n,mem_ck,mem_ck_n,mem_cke,mem_cs_n,mem_ras_n,mem_cas_n,mem_we_n,mem_odt;
    wire [14:0] mem_a;wire [2:0] mem_ba;tri [3:0] mem_dqs,mem_dqs_n;tri [31:0] mem_dq;wire [3:0] mem_dm;
    board1080_top dut(
        .clk_27m(clk_27m),.clk_p(clk_27m),.clk_n(!clk_27m),.reset_n(reset_n),
        .pixclk_in(clk_27m),.vs_in(1'b0),.hs_in(1'b0),.de_in(1'b0),.r_in(8'd0),.g_in(8'd0),.b_in(8'd0),
        .pix_clk(pix_clk),.hs_out(hs_out),.vs_out(vs_out),.de_out(de_out),.r_out(r_out),.g_out(g_out),.b_out(b_out),
        .hd_scl(hd_scl),.hd_sda(hd_sda),.rstn_out(rstn_out),.led(led),
        .mem_rst_n(mem_rst_n),.mem_ck(mem_ck),.mem_ck_n(mem_ck_n),.mem_cke(mem_cke),.mem_cs_n(mem_cs_n),
        .mem_ras_n(mem_ras_n),.mem_cas_n(mem_cas_n),.mem_we_n(mem_we_n),.mem_odt(mem_odt),
        .mem_a(mem_a),.mem_ba(mem_ba),.mem_dqs(mem_dqs),.mem_dqs_n(mem_dqs_n),.mem_dq(mem_dq),.mem_dm(mem_dm));
    integer active_case=0,events,summary,cold_power_cycles=0,began,waited,common_resets=0;
    reg runtime_active=0;
    task event_row(input [8*40-1:0] name);
        begin
            $fdisplay(events,"%0s,%0d,%0d,%0d,%0d,%02h,%0d,%0d,%0d,%0d,%0d,%0d",name,active_case,
                dut.global_reset_n,dut.pipeline_reset_n,dut.board_failed,dut.board_fault,
                led[7],dut.u_ddr3_test_h.axi_awvalid,dut.system.capture_admit,
                dut.system.scan_enable,dut.system.external_fault,dut.u_ddr3_test_h.resetn);
            $fflush(events);
        end
    endtask
    task healthy;
        begin
            dut.configuration_pll.test_lock=1;dut.video_pll.test_lock=1;
            dut.hdmi_configuration.test_rx_done=1;dut.hdmi_configuration.test_tx_done=1;
            dut.hdmi_configuration.test_failed=0;dut.hdmi_configuration.test_error=0;
            dut.u_ddr3_test_h.test_pll_lock=1;dut.u_ddr3_test_h.test_init_done=1;
            dut.input_status.test_qualified=1;dut.input_status.test_failed=0;
            dut.system.test_failed=0;dut.system.test_aw_hold=0;
        end
    endtask
    task power_up;
        begin
            began=ticks;@(negedge clk_27m);reset_n=1;
            repeat(1000000)@(negedge clk_27m);
            if(dut.global_reset_n)$fatal(1,"Bound baseline power delay shortened");
            waited=0;
            while(!dut.global_reset_n && waited<100000)begin @(negedge clk_27m);waited=waited+1;end
            if(!dut.global_reset_n)$fatal(1,"Common power reset did not release");
            if(active_case==1)cold_power_cycles=ticks-began;
            repeat(16)@(negedge clk_27m);
        end
    endtask
    task common_reset;
        begin
            @(negedge clk_27m);runtime_active=0;reset_n=0;#1;
            if(dut.pipeline_reset_n || dut.board_failed || dut.awvalid || mem_rst_n || led[7])
                $fatal(1,"Common reset did not clear sticky board/transaction state");
            common_resets=common_resets+1;
            event_row("common_reset_clears");
            repeat(12)@(negedge clk_27m);
        end
    endtask
    task blocked_a7;
        begin
            if(!dut.board_failed || dut.board_fault!==8'ha7 || !led[7] ||
               dut.pipeline_release || dut.pipeline_reset_n || !mem_rst_n ||
               dut.system.capture_admit || dut.system.scan_enable)
                $fatal(1,"Startup HDMI failure must latch visible A7 without starting pipeline");
        end
    endtask
    task runtime_quarantine;
        begin
            if(!dut.board_failed || dut.board_fault!==8'ha7 || !led[7] ||
               !dut.pipeline_release || !dut.pipeline_reset_n || !mem_rst_n ||
               dut.system.capture_admit || dut.system.scan_enable || !dut.system.external_fault ||
               dut.system.external_fault_code!==8'ha7 || !dut.awvalid ||
               dut.u_ddr3_test_h.axi_awaddr!==28'd2097152 || dut.u_ddr3_test_h.axi_awlen!==4'd15)
                $fatal(1,"Late HDMI fault must use A7 admission/drain path with AW and resets preserved");
        end
    endtask
    always @(posedge clk_27m)begin
        ticks=ticks+1;
        if(ticks>4500000)$fatal(1,"Bounded checked-control test exceeded4.5M clocks");
        if(runtime_active && (!dut.pipeline_reset_n || !mem_rst_n || !dut.awvalid))
            $fatal(1,"Fault withdrew outstanding AW or reset live pipeline/DDR");
    end
    always @(negedge dut.pipeline_reset_n)
        if(runtime_active && reset_n)$fatal(1,"Runtime fault reset live pipeline");
    initial begin
        events=$fopen("checked-control-events.csv","w");
        if(!events)$fatal(1,"Could not create event receipt");
        $fdisplay(events,"event,case,global_reset_n,pipeline_reset_n,board_failed,board_fault,led7,physical_stub_awvalid,capture_admit,scan_enable,external_fault,ddr_reset_n");
        repeat(8)@(negedge clk_27m);healthy();

        active_case=1;dut.hdmi_configuration.test_rx_done=0;dut.hdmi_configuration.test_tx_done=0;
        dut.hdmi_configuration.test_failed=1;dut.hdmi_configuration.test_error=4'h1;
        power_up();blocked_a7();event_row("initial_failure_blocked");
        healthy();repeat(16)@(negedge clk_27m);blocked_a7();event_row("initial_failure_sticky");
        common_reset();

        active_case=2;healthy();dut.hdmi_configuration.test_rx_done=0;dut.hdmi_configuration.test_tx_done=0;
        power_up();
        // Deliberately contradictory simultaneous status assumptions prove
        // the board fault wins independently of wrapper completion gating.
        @(negedge clk_27m);dut.hdmi_configuration.test_rx_done=1;dut.hdmi_configuration.test_tx_done=1;
        dut.hdmi_configuration.test_failed=1;dut.hdmi_configuration.test_error=4'h4;
        repeat(16)@(negedge clk_27m);blocked_a7();event_row("simultaneous_ready_failure");
        common_reset();

        active_case=3;healthy();power_up();
        if(!dut.pipeline_reset_n || !dut.system.capture_admit || dut.board_failed)
            $fatal(1,"Clean common-reset epoch did not admit pipeline");
        event_row("healthy_admitted");
        @(negedge clk_27m);dut.system.test_aw_hold=1;
        repeat(4)@(negedge clk_27m);runtime_active=1;
        @(negedge dut.cfg_clk);dut.hdmi_configuration.test_failed=1;dut.hdmi_configuration.test_error=4'h5;
        // Actual wrapper clears completion in the same cfg-domain failure.
        dut.hdmi_configuration.test_rx_done=0;dut.hdmi_configuration.test_tx_done=0;
        repeat(20)@(negedge clk_27m);runtime_quarantine();event_row("late_failure_held_aw");
        dut.hdmi_configuration.test_failed=0;dut.hdmi_configuration.test_error=0;
        dut.hdmi_configuration.test_rx_done=1;dut.hdmi_configuration.test_tx_done=1;
        repeat(20)@(negedge clk_27m);runtime_quarantine();event_row("late_failure_sticky");
        dut.system.test_failed=1;dut.input_status.test_failed=1;
        repeat(20)@(negedge clk_27m);runtime_quarantine();event_row("first_failure_preserved");
        common_reset();

        active_case=4;healthy();power_up();
        if(!dut.pipeline_reset_n || dut.board_failed || led[7] || !dut.system.capture_admit)
            $fatal(1,"Fresh common reset did not recover from sticky A7");
        event_row("common_reset_recovery");
        summary=$fopen("summary.json","w");
        $fdisplay(summary,"{\"Passed\":true,\"StartupFailureCases\":2,\"LateFailureHeldAWCases\":1,\"CommonResets\":%0d,\"ColdPowerReferenceCycles\":%0d,\"ActualCheckedTopExecuted\":true,\"TestOnlyIPStubs\":true,\"PipelineResetMonotonic\":true,\"DDRResetPreserved\":true,\"PhysicalI2CVerified\":false,\"ActualSystemDatapathVerified\":false,\"HardwareAccessed\":false}",common_resets,cold_power_cycles);
        $fclose(summary);$fclose(events);
        $display("BOARD1080_CHECKED_CONTROL_SIM_PASS startup2 lateA7 heldAW commonreset3 recovery");
        $finish;
    end
endmodule

// Explicit status-only stub: no implementation body of ms72xx_checked_ctl.
module ms72xx_checked_ctl #(
    parameter integer CLK_FRE=10000000,IIC_FREQ=400000,TIMEOUT_CYCLES=CLK_FRE/100
)(
    input wire clk,rst_n,output wire init_over_rx,init_over,init_failed,
    output wire [3:0] error_code,inout wire iic_scl,iic_sda
);
    reg test_rx_done=0,test_tx_done=0,test_failed=0;reg [3:0] test_error=0;
    assign init_over_rx=rst_n && test_rx_done;
    assign init_over=rst_n && test_tx_done;
    assign init_failed=rst_n && test_failed;
    assign error_code=rst_n ? test_error : 4'h0;
    assign iic_scl=1'bz;assign iic_sda=1'bz;
endmodule
