`timescale 1ns/1ps
// Actual new top + sampler; only PLL/DDR/IIC/system bodies are opaque stubs.
module tb_hdmi_camera_pixel_control;
    reg clk_27m=0,reset_n=0,pclk=0,run_pclk=0;
    always #18.5185 clk_27m=~clk_27m;
    always begin #3.367;if(run_pclk)pclk=~pclk;else pclk=0;end
    reg raw_vs=1,raw_hs=1,raw_de=1;
    reg [23:0] raw_rgb=24'hf78123;
    tri1 hd_scl,hd_sda,default_scl,default_sda;
    wire pix_clk,rstn_out,mem_rst_n;
    wire [7:0] led;
    hdmi_camera_pixel_top #(.INPUT_TIMING_CONFIGURED(1),.CFG_SETTLE_CYCLES(1),
        .PCLK_STALE_REF_CYCLES(65536)) dut(
        .clk_27m(clk_27m),.clk_p(clk_27m),.clk_n(!clk_27m),.reset_n(reset_n),
        .pixclk_in(pclk),.vs_in(raw_vs),.hs_in(raw_hs),.de_in(raw_de),
        .r_in(raw_rgb[23:16]),.g_in(raw_rgb[15:8]),.b_in(raw_rgb[7:0]),
        .pix_clk(pix_clk),.hs_out(),.vs_out(),.de_out(),.r_out(),.g_out(),.b_out(),
        .hd_scl(hd_scl),.hd_sda(hd_sda),.rstn_out(rstn_out),.led(led),.mem_rst_n(mem_rst_n),
        .mem_ck(),.mem_ck_n(),.mem_cke(),.mem_cs_n(),.mem_ras_n(),.mem_cas_n(),.mem_we_n(),.mem_odt(),
        .mem_a(),.mem_ba(),.mem_dqs(),.mem_dqs_n(),.mem_dq(),.mem_dm());
    // No INPUT_TIMING_CONFIGURED override: the canonical default stays 0.
    hdmi_camera_pixel_top #(.CFG_SETTLE_CYCLES(1),.PCLK_STALE_REF_CYCLES(65536)) not_configured(
        .clk_27m(clk_27m),.clk_p(clk_27m),.clk_n(!clk_27m),.reset_n(reset_n),
        .pixclk_in(pclk),.vs_in(raw_vs),.hs_in(raw_hs),.de_in(raw_de),
        .r_in(raw_rgb[23:16]),.g_in(raw_rgb[15:8]),.b_in(raw_rgb[7:0]),
        .pix_clk(),.hs_out(),.vs_out(),.de_out(),.r_out(),.g_out(),.b_out(),
        .hd_scl(default_scl),.hd_sda(default_sda),.rstn_out(),.led(),.mem_rst_n(),
        .mem_ck(),.mem_ck_n(),.mem_cke(),.mem_cs_n(),.mem_ras_n(),.mem_cas_n(),.mem_we_n(),.mem_odt(),
        .mem_a(),.mem_ba(),.mem_dqs(),.mem_dqs_n(),.mem_dq(),.mem_dm());
    integer ticks=0,case_id=0,waited,started,cold_cycles=0,warm_shortcuts=0;
    integer runtime_cases=0,reset_cases=0,bundle_checks=0;
    reg live_epoch=0,aw_must_hold=0;
    always @(posedge clk_27m)begin
        ticks=ticks+1;
        if(ticks>2200000)$fatal(1,"bounded pixel control test timeout");
        if(not_configured.pipeline_release || not_configured.system.capture_admit || not_configured.system.scan_enable)
            $fatal(1,"default compile configuration admitted a pipeline");
        if(live_epoch && reset_n && (!dut.pipeline_reset_n || !mem_rst_n))
            $fatal(1,"runtime fault reset live pipeline or DDR");
        if(aw_must_hold && (!dut.awvalid || dut.awaddr!==28'd2097152 || dut.awlen!==4'd15 ||
            dut.wstrb!==32'hffffffff || dut.wdata!==256'h123456789abcdef00123456789abcdef0123456789abcdef0123456789abcdef0))
            $fatal(1,"runtime fault withdrew or changed a held DDR AW/data");
    end
    always @(negedge dut.pipeline_reset_n)
        if(live_epoch && reset_n)$fatal(1,"pipeline release was not monotonic in a live epoch");
    always @(posedge pclk)begin
        #0.001;
        if(dut.sampled_valid)begin
            if(dut.system.pix_in_rgb!==dut.sampled_rgb || dut.system.pix_in_de!==dut.input_de_active ||
               dut.system.pix_in_vsync_active!==dut.input_vs_active)
                $fatal(1,"top did not feed the common sampled bundle to the video system");
            if(dut.system.cfg_out_cx!==24'sd245632 || dut.system.cfg_out_cy!==24'sd138112 ||
               dut.system.cfg_src_cx!==24'sd245632 || dut.system.cfg_src_cy!==24'sd138112 ||
               dut.system.cfg_src_fx!==24'sd262144 || dut.system.cfg_src_fy!==24'sd262144 ||
               dut.system.cfg_inv_fx!==32'sd1048576 || dut.system.cfg_inv_fy!==32'sd1048576 ||
               dut.system.cfg_k1!==0 || dut.system.cfg_k2!==0 || dut.system.cfg_k3!==0 ||
               dut.system.cfg_p1!==0 || dut.system.cfg_p2!==0)
                $fatal(1,"top identity configuration differs");
            bundle_checks=bundle_checks+1;
        end
    end
    task refs(input integer n);repeat(n)begin @(negedge clk_27m);#0.01;end endtask
    task healthy;
        begin
            dut.configuration_pll.test_lock=1;dut.video_pll.test_lock=1;
            dut.hdmi_configuration.test_rx_done=1;dut.hdmi_configuration.test_tx_done=1;
            dut.hdmi_configuration.test_failed=0;dut.hdmi_configuration.test_error=0;
            dut.u_ddr3_test_h.test_init_done=1;dut.u_ddr3_test_h.test_pll_lock=1;
            dut.system.test_failed=0;dut.system.test_fault=0;dut.system.test_aw_hold=0;
            not_configured.configuration_pll.test_lock=1;not_configured.video_pll.test_lock=1;
            not_configured.hdmi_configuration.test_rx_done=1;not_configured.hdmi_configuration.test_tx_done=1;
            not_configured.hdmi_configuration.test_failed=0;
            not_configured.u_ddr3_test_h.test_init_done=1;not_configured.u_ddr3_test_h.test_pll_lock=1;
        end
    endtask
    task power_up(input integer cold);
        begin
            started=ticks;@(negedge clk_27m);reset_n=1;
            if(cold)begin
                refs(1000000);if(dut.global_reset_n)$fatal(1,"cold power delay was shortened");
            end else begin
                // Timing-only warm shortcut, explicitly reported. The cold
                // epoch above executes the unchanged million-cycle counter.
                refs(6);dut.power_count=20'hfffff;not_configured.power_count=20'hfffff;
                warm_shortcuts=warm_shortcuts+1;
            end
            waited=0;
            while(!dut.global_reset_n && waited<100000)begin refs(1);waited=waited+1;end
            if(!dut.global_reset_n)$fatal(1,"global power reset did not release");
            if(cold)cold_cycles=ticks-started;
            refs(24);
        end
    endtask
    task wait_admit;
        begin
            waited=0;
            while(!dut.pipeline_reset_n && waited<20000)begin refs(1);waited=waited+1;end
            refs(12);
            if(!dut.pipeline_reset_n || !dut.pclk_observed || dut.board_failed ||
               !dut.system.capture_admit || !dut.system.scan_enable || !mem_rst_n)
                $fatal(1,"healthy configured timing did not admit after actual PCLK activity");
            live_epoch=1;
        end
    endtask
    task hold_aw;
        begin dut.system.test_aw_hold=1;refs(4);aw_must_hold=1;end
    endtask
    task quarantine(input [7:0] expected_fault);
        begin
            if(!dut.board_failed || dut.board_fault!==expected_fault || !led[7] ||
               !dut.pipeline_release || !dut.pipeline_reset_n || !mem_rst_n ||
               dut.system.capture_admit || dut.system.scan_enable || !dut.system.external_fault ||
               dut.system.external_fault_code!==expected_fault)
                $fatal(1,"runtime quarantine differs case=%0d fault=%h expected=%h",case_id,dut.board_fault,expected_fault);
        end
    endtask
    task common_reset;
        begin
            @(negedge clk_27m);live_epoch=0;aw_must_hold=0;reset_n=0;#0.01;
            if(dut.pipeline_release || dut.board_failed || dut.pclk_observed || dut.pclk_divider!==0 ||
               dut.sampled_valid || mem_rst_n || dut.awvalid)
                $fatal(1,"common reset retained old activity, valid data or DDR ownership");
            refs(8);reset_cases=reset_cases+1;
        end
    endtask
    reg [7:0] code;
    initial begin
        refs(8);healthy();
        // Fast cfg settle plus no input clock must NEVER admit, even before
        // the stale timeout. This directly covers the original draft hole.
        power_up(1);refs(70000);
        if(dut.pipeline_release || dut.pclk_observed || dut.system.capture_admit || !mem_rst_n)
            $fatal(1,"no-PCLK startup became admitted");
        $display("HDMI_PIXEL_CONTROL_CASE default_off no_pclk_fast_cfg_blocked cold_cycles=%0d",cold_cycles);
        dut.hdmi_configuration.test_failed=1;dut.hdmi_configuration.test_error=4'h4;
        run_pclk=1;refs(8000);
        if(!dut.pclk_observed || !dut.board_failed || dut.board_fault!==8'ha7 || dut.pipeline_release)
            $fatal(1,"simultaneous ready/config-failure startup was admitted");
        dut.hdmi_configuration.test_failed=0;refs(16);
        if(!dut.board_failed || dut.pipeline_release)$fatal(1,"startup failure was not sticky");
        $display("HDMI_PIXEL_CONTROL_CASE startup_failure_wins_ready sticky_a7");
        common_reset();healthy();power_up(0);
        run_pclk=1;wait_admit();
        if(dut.hs_transition_seen)$fatal(1,"initial high HS invented an activity edge");
        @(negedge pclk);raw_hs=0;raw_rgb=24'h12c9fe;refs(4);
        if(!dut.hs_transition_seen)$fatal(1,"actual registered HS transition was not observed");
        $display("HDMI_PIXEL_CONTROL_CASE common_bundle_identity first_high_hs_baseline");
        // Six independent fault epochs. All held AW/data are routed through
        // the actual top; stub DDR never accepts them. No DDR drain is claimed.
        for(case_id=0;case_id<6;case_id=case_id+1)begin
            if(case_id!=0)begin
                common_reset();healthy();power_up(0);run_pclk=1;wait_admit();
            end
            hold_aw();
            case(case_id)
                0:begin code=8'ha7;dut.hdmi_configuration.test_failed=1;dut.hdmi_configuration.test_error=4'h5;
                    dut.hdmi_configuration.test_rx_done=0;dut.hdmi_configuration.test_tx_done=0;end
                1:begin code=8'ha1;@(negedge pclk);run_pclk=0;refs(65550);end
                2:begin code=8'ha3;dut.u_ddr3_test_h.test_init_done=0;end
                3:begin code=8'ha4;dut.video_pll.test_lock=0;end
                4:begin code=8'ha5;dut.hdmi_configuration.test_tx_done=0;end
                5:begin code=8'ha6;dut.system.test_failed=1;dut.system.test_fault=8'he1;end
            endcase
            refs(24);quarantine(code);
            // Restore predicates and introduce a second failure. Neither may
            // erase/replace the first sticky code or restart an epoch.
            dut.hdmi_configuration.test_failed=0;dut.hdmi_configuration.test_rx_done=1;
            dut.hdmi_configuration.test_tx_done=1;dut.u_ddr3_test_h.test_init_done=1;
            dut.video_pll.test_lock=1;dut.system.test_failed=0;run_pclk=1;
            refs(48);quarantine(code);dut.system.test_failed=1;refs(16);quarantine(code);
            runtime_cases=runtime_cases+1;
            $display("HDMI_PIXEL_CONTROL_CASE runtime_fault=%h held_aw sticky_no_local_reset",code);
        end
        // A retained source divider=1 cannot satisfy a new reset epoch when
        // input PCLK is stopped. Its common async clear is essential here.
        waited=0;while(!dut.pclk_divider[15] && waited<20000)begin refs(1);waited=waited+1;end
        if(!dut.pclk_divider[15])$fatal(1,"failed to establish old heartbeat1");
        @(negedge pclk);run_pclk=0;common_reset();healthy();power_up(0);refs(100);
        if(dut.pclk_observed || dut.pipeline_release || dut.pclk_divider!==0)
            $fatal(1,"retained old heartbeat faked new PCLK activity");
        run_pclk=1;wait_admit();refs(12);
        if(dut.board_failed || led[7])$fatal(1,"common reset did not recover a clean epoch");
        $display("HDMI_PIXEL_CONTROL_CASE stopped_old_heartbeat_reset clean_common_reset_recovery");
        if(runtime_cases!=6 || reset_cases!=7 || bundle_checks<1000 || cold_cycles<1000000)
            $fatal(1,"pixel control coverage incomplete");
        $display("HDMI_PIXEL_CONTROL_PASS runtime_cases=%0d common_resets=%0d cold_cycles=%0d warm_shortcuts=%0d bundle_checks=%0d",runtime_cases,reset_cases,cold_cycles,warm_shortcuts,bundle_checks);
        $finish;
    end
endmodule
