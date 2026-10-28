`timescale 1ps/1ps
// CONTROL-ONLY: actual board1080_top, opaque TEST-ONLY IP/status/System stubs.
// This proves wiring/qualification/reset intent, NOT FIFO/DDR/PHY/data function.
module tb_board1080_control;
    reg clk_27m=0,reset_n=0;
    integer phase=0,delay_ps,ref_ticks=0;
    initial forever begin
        phase=phase+500000;delay_ps=phase/27;phase=phase%27;
        #(delay_ps)clk_27m=~clk_27m;
    end
    wire pix_clk,hs_out,vs_out,de_out,hd_scl,rstn_out;
    wire [7:0] r_out,g_out,b_out,led;tri hd_sda;
    wire mem_rst_n,mem_ck,mem_ck_n,mem_cke,mem_cs_n,mem_ras_n,mem_cas_n,mem_we_n,mem_odt;
    wire [14:0] mem_a;wire [2:0] mem_ba;tri [3:0] mem_dqs,mem_dqs_n;tri [31:0] mem_dq;wire [3:0] mem_dm;
    // Stub differential input/core/config/video clocks intentionally alias27MHz.
    // There is no actual input raster because the status/System are opaque.
    board1080_top dut(
        .clk_27m(clk_27m),.clk_p(clk_27m),.clk_n(!clk_27m),.reset_n(reset_n),
        .pixclk_in(clk_27m),.vs_in(1'b0),.hs_in(1'b0),.de_in(1'b0),.r_in(8'd0),.g_in(8'd0),.b_in(8'd0),
        .pix_clk(pix_clk),.hs_out(hs_out),.vs_out(vs_out),.de_out(de_out),.r_out(r_out),.g_out(g_out),.b_out(b_out),
        .hd_scl(hd_scl),.hd_sda(hd_sda),.rstn_out(rstn_out),.led(led),
        .mem_rst_n(mem_rst_n),.mem_ck(mem_ck),.mem_ck_n(mem_ck_n),.mem_cke(mem_cke),.mem_cs_n(mem_cs_n),
        .mem_ras_n(mem_ras_n),.mem_cas_n(mem_cas_n),.mem_we_n(mem_we_n),.mem_odt(mem_odt),
        .mem_a(mem_a),.mem_ba(mem_ba),.mem_dqs(mem_dqs),.mem_dqs_n(mem_dqs_n),.mem_dq(mem_dq),.mem_dm(mem_dm));
    integer startup_blocks=0,runtime_cases=0,sticky_cases=0,common_resets=0,held_aw_cases=0;
    integer cold_power_cycles=0,active_case=0,events,summary,k;
    reg runtime_active=0;reg [7:0] observed_fault=0;
    reg [63:0] start_ps,end_ps;

    task automatic event_row(input [8*32-1:0] event_name);
        begin
            $fdisplay(events,"%0s,%0d,%0d,%0d,%0d,%0d,%02x,%0d,%0d,%0d,%0d",event_name,active_case,$time,
                dut.global_reset_n,dut.pipeline_reset_n,dut.board_failed,dut.board_fault,
                dut.u_ddr3_test_h.axi_awvalid,dut.system.capture_admit,dut.system.scan_enable,dut.system.external_fault);
            $fflush(events);
        end
    endtask
    task automatic flags_low;
        begin
            dut.configuration_pll.test_lock=0;dut.video_pll.test_lock=0;
            dut.hdmi_configuration.test_rx_done=0;dut.hdmi_configuration.test_tx_done=0;
            dut.u_ddr3_test_h.test_pll_lock=0;dut.u_ddr3_test_h.test_init_done=0;
            dut.input_status.test_qualified=0;dut.input_status.test_failed=0;dut.input_status.test_fault=0;
            dut.system.test_failed=0;dut.system.test_fault=0;
        end
    endtask
    task automatic healthy_flags;
        begin
            dut.configuration_pll.test_lock=1;dut.video_pll.test_lock=1;
            dut.hdmi_configuration.test_rx_done=1;dut.hdmi_configuration.test_tx_done=1;
            dut.u_ddr3_test_h.test_pll_lock=1;dut.u_ddr3_test_h.test_init_done=1;
            dut.input_status.test_qualified=1;dut.input_status.test_failed=0;dut.input_status.test_fault=0;
            dut.system.test_failed=0;dut.system.test_fault=0;
        end
    endtask
    task automatic wait_power;
        integer began,waited;begin
            began=ref_ticks;start_ps=$time;
            repeat(1000000)@(negedge clk_27m);
            if(dut.global_reset_n)$fatal(1,"real board power delay released before one million27MHz clocks");
            waited=0;
            while(!dut.global_reset_n&&waited<100000)begin @(negedge clk_27m);waited=waited+1;end
            if(!dut.global_reset_n)$fatal(1,"real board20bit power delay did not release within1.1M clocks");
            end_ps=$time;
            if(active_case==0)cold_power_cycles=ref_ticks-began;
            event_row("power_delay_released");
        end
    endtask
    task automatic wait_admitted;
        integer waited;begin
            waited=0;
            while(!dut.pipeline_release&&waited<100)begin @(negedge clk_27m);waited=waited+1;end
            repeat(12)@(negedge clk_27m);
            if(!dut.pipeline_release||dut.board_failed||!dut.system.rst_n||!dut.u_ddr3_test_h.resetn||
               !dut.system.capture_admit||!dut.system.scan_enable||dut.system.external_fault)
                $fatal(1,"complete assumed qualifications did not release real top control");
            event_row("pipeline_admitted");
        end
    endtask
    task automatic assert_quarantined(input [7:0] code);
        begin
            if(!dut.board_failed||dut.board_fault!==code||!dut.pipeline_release||!dut.pipeline_reset_n||
               !dut.system.rst_n||!dut.u_ddr3_test_h.resetn||dut.system.capture_admit||dut.system.scan_enable||
               !dut.system.external_fault||dut.system.external_fault_code!==code)
                $fatal(1,"runtime fault did not stop admissions while preserving common reset code=%h",code);
            if(!dut.system.awvalid||!dut.u_ddr3_test_h.axi_awvalid||dut.u_ddr3_test_h.axi_awaddr!==28'd2097152||
               dut.u_ddr3_test_h.axi_awlen!==4'd15||dut.u_ddr3_test_h.axi_wdata!==dut.system.wdata)
                $fatal(1,"board boundary withdrew/changed the stub's outstanding AW request on runtime fault");
        end
    endtask
    task automatic common_reset;
        begin
            @(negedge clk_27m);runtime_active=0;reset_n=0;
            #1;
            if(dut.pipeline_reset_n||dut.system.rst_n||dut.u_ddr3_test_h.resetn||dut.awvalid||dut.board_failed)
                $fatal(1,"common reset did not reach actual board control and both opaque transaction endpoints");
            common_resets=common_resets+1;event_row("common_reset_asserted");
            dut.system.test_aw_hold=0;
            repeat(12)@(negedge clk_27m);
        end
    endtask
    always @(posedge clk_27m)begin
        ref_ticks=ref_ticks+1;
        if(ref_ticks>7000000)$fatal(1,"bounded control-only regression exceeded7M reference clocks");
        if(runtime_active)begin
            if(!dut.pipeline_reset_n||!dut.system.rst_n||!dut.u_ddr3_test_h.resetn)
                $fatal(1,"runtime flag locally reset the system or DDR endpoint");
            if(!dut.u_ddr3_test_h.axi_awvalid||dut.u_ddr3_test_h.axi_awaddr!==28'd2097152||dut.u_ddr3_test_h.axi_awlen!==4'd15)
                $fatal(1,"held test-only AW lost at actual board wiring boundary");
        end
    end
    always @(negedge dut.pipeline_reset_n)
        if(runtime_active&&reset_n)$fatal(1,"runtime qualification glitch reset the transaction domain");

    initial begin
        events=$fopen("control-events.csv","w");
        $fdisplay(events,"event,case,time_ps,global_reset_n,pipeline_reset_n,board_failed,board_fault,physical_stub_awvalid,capture_admit,scan_enable,external_fault");
        flags_low();dut.system.test_aw_hold=0;
        repeat(8)@(negedge clk_27m);reset_n=1;wait_power();
        // Test each missing qualification against an otherwise healthy assumed
        // environment. Flush low flags between cases to avoid an all-good gap.
        for(k=0;k<7;k=k+1)begin
            active_case=k;
            @(negedge clk_27m);healthy_flags();
            case(k)
                0:dut.configuration_pll.test_lock=0;
                1:dut.video_pll.test_lock=0;
                2:dut.hdmi_configuration.test_rx_done=0;
                3:dut.hdmi_configuration.test_tx_done=0;
                4:dut.u_ddr3_test_h.test_init_done=0;
                5:dut.u_ddr3_test_h.test_pll_lock=0;
                6:dut.input_status.test_qualified=0;
            endcase
            repeat(12)@(negedge clk_27m);
            if(dut.pipeline_release||dut.pipeline_reset_n||dut.board_failed)$fatal(1,"missing startup qualifier was admitted case=%0d",k);
            startup_blocks=startup_blocks+1;event_row("missing_qualifier_blocked");
            flags_low();repeat(12)@(negedge clk_27m);
        end
        active_case=0;healthy_flags();wait_admitted();
        for(active_case=1;active_case<=6;active_case=active_case+1)begin
            if(active_case!=1)begin
                healthy_flags();@(negedge clk_27m);reset_n=1;wait_power();wait_admitted();
            end
            @(negedge clk_27m);dut.system.test_aw_hold=1;
            repeat(4)@(negedge clk_27m);runtime_active=1;event_row("held_aw_before_fault");
            case(active_case)
                1:begin dut.input_status.test_fault=8'h11;dut.input_status.test_failed=1;end
                2:dut.input_status.test_qualified=0;
                3:dut.u_ddr3_test_h.test_init_done=0;
                4:dut.configuration_pll.test_lock=0;
                // RX loss also resets the observer, so this unambiguous A5
                // case drops TX completion while keeping RX/status healthy.
                5:dut.hdmi_configuration.test_tx_done=0;
                6:begin dut.system.test_fault=8'h55;dut.system.test_failed=1;end
            endcase
            repeat(16)@(negedge clk_27m);observed_fault=8'ha0+active_case;
            assert_quarantined(observed_fault);runtime_cases=runtime_cases+1;held_aw_cases=held_aw_cases+1;
            event_row("runtime_fault_quarantined");
            healthy_flags();repeat(16)@(negedge clk_27m);assert_quarantined(observed_fault);
            if(active_case==1)dut.system.test_failed=1;else dut.input_status.test_failed=1;
            repeat(16)@(negedge clk_27m);assert_quarantined(observed_fault);sticky_cases=sticky_cases+1;
            event_row("first_fault_still_sticky");
            healthy_flags();common_reset();
            $display("PASS board1080 control runtime A%0d: assumed flag, actual sticky top, held AW route, no local system reset, common reset",active_case);
        end
        if(startup_blocks!=7||runtime_cases!=6||sticky_cases!=6||held_aw_cases!=6||common_resets!=6||cold_power_cycles<1000000||cold_power_cycles>1100000)
            $fatal(1,"control-only coverage incomplete");
        summary=$fopen("summary.json","w");
        $fdisplay(summary,"{\"passed\":true,\"test_only_stubs\":true,\"startup_missing_qualifiers_blocked\":%0d,\"runtime_fault_cases\":%0d,\"first_fault_sticky_cases\":%0d,\"held_stub_aw_routing_cases\":%0d,\"common_reset_cases\":%0d,\"cold_power_delay_reference_cycles\":%0d,\"reference_cycles\":%0d,\"actual_system_datapath_verified\":false,\"actual_fifo_verified\":false,\"physical_ddr_or_pll_or_iic_verified\":false,\"clock_stop_recovery_verified\":false}",startup_blocks,runtime_cases,sticky_cases,held_aw_cases,common_resets,cold_power_cycles,ref_ticks);
        $fclose(summary);$fclose(events);
        $display("PASS board1080 control: real top qualification/once-release/A1-A6/no-reset/held-stub-AW/common-reset; all IP/status/System data are explicit assumptions");
        $finish;
    end
endmodule
