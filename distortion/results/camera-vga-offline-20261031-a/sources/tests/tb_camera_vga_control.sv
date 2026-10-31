`timescale 1ps/1ps
// Actual board control plus real capture_warmup; sensor/System and physical IP
// are explicit status stubs. No image, SCCB or memory transaction is modeled.
module tb_camera_vga_control;
    localparam WARMUP_MS=8,WAIT_CYCLES=27000*WARMUP_MS;
    reg clk_27m=0,clk_p=0,reset_n=0,cam_pclk=0;
    integer clock_phase=0,clock_delay;
    initial forever begin
        clock_phase=clock_phase+500000;clock_delay=clock_phase/27;
        clock_phase=clock_phase%27;#(clock_delay)clk_27m=~clk_27m;
    end
    always #4000 clk_p=~clk_p;
    always #10417 cam_pclk=~cam_pclk;
    tri1 cam_rst_n,cam_scl,cam_sda,hd_scl,hd_sda;
    wire pix_clk,hs_out,vs_out,de_out,rstn_out;
    wire [7:0] r_out,g_out,b_out,led;
    wire mem_rst_n,mem_ck,mem_ck_n,mem_cke,mem_cs_n,mem_ras_n,mem_cas_n,mem_we_n,mem_odt;
    wire [14:0] mem_a;wire [2:0] mem_ba;wire [3:0] mem_dm;
    tri [3:0] mem_dqs,mem_dqs_n;tri [31:0] mem_dq;
    camera_vga_output_top #(.CAMERA_WARMUP_MS(WARMUP_MS)) dut(
        .clk_27m(clk_27m),.clk_p(clk_p),.clk_n(!clk_p),.reset_n(reset_n),
        .cam_pclk(cam_pclk),.cam_vsync(1'b1),.cam_href(1'b1),.cam_data(8'h00),
        .cam_rst_n(cam_rst_n),.cam_scl(cam_scl),.cam_sda(cam_sda),
        .pix_clk(pix_clk),.hs_out(hs_out),.vs_out(vs_out),.de_out(de_out),
        .r_out(r_out),.g_out(g_out),.b_out(b_out),.hd_scl(hd_scl),.hd_sda(hd_sda),
        .rstn_out(rstn_out),.led(led),.mem_rst_n(mem_rst_n),.mem_ck(mem_ck),
        .mem_ck_n(mem_ck_n),.mem_cke(mem_cke),.mem_cs_n(mem_cs_n),
        .mem_ras_n(mem_ras_n),.mem_cas_n(mem_cas_n),.mem_we_n(mem_we_n),.mem_odt(mem_odt),
        .mem_a(mem_a),.mem_ba(mem_ba),.mem_dqs(mem_dqs),.mem_dqs_n(mem_dqs_n),
        .mem_dq(mem_dq),.mem_dm(mem_dm));

    integer startup_cases=0,runtime_cases=0,reset_checks=0,release_events=0;
    integer led_checks=0,chatter_checks=0,ready_run=0;
    reg previous_release=0;
    // Independent interval monitor: no release before a complete uninterrupted
    // reference-domain readiness interval. Runtime failures must retain reset.
    always @(posedge clk_27m) begin
        if(!dut.global_reset_n || !dut.ref_reset[1] || !dut.camera_ready ||
           dut.camera_failed || !dut.video_lock_ref[1] || !dut.ddr_ready_ref[1] || !dut.tx_init_done)
            ready_run=0;
        else ready_run=ready_run+1;
        #1;
        if(dut.global_reset_n && previous_release && !dut.pipeline_reset_n)
            $fatal(1,"runtime failure withdrew common pipeline reset");
        if(dut.pipeline_release && !previous_release)begin
            if(ready_run<WAIT_CYCLES)$fatal(1,"pipeline released before continuous warmup %0d",ready_run);
            release_events=release_events+1;
        end
        previous_release=dut.pipeline_release;
    end

    task ticks(input integer n);
        repeat(n)@(negedge clk_27m);
    endtask
    task healthy;
        begin
            dut.video_pll.test_lock=1;
            dut.u_ddr3_test_h.test_init_done=1;dut.u_ddr3_test_h.test_pll_lock=1;
            dut.hdmi_configuration.test_ready=1;dut.hdmi_configuration.test_error=0;
            dut.camera_configuration.test_ready=1;dut.camera_configuration.test_failed=0;
            dut.camera_configuration.test_error=0;
            dut.system.test_failed=0;dut.system.test_fault=0;
            dut.system.test_captured_frames=0;dut.system.test_processed_frames=0;
        end
    endtask
    task common_reset;
        begin
            reset_n=0;healthy();ticks(8);
            if(dut.pipeline_reset_n!==0 || dut.pipeline_release!==0 || dut.board_failed!==0 ||
               dut.board_fault!==0 || dut.core_reset!==0 || dut.board_failed_core!==0)
                $fatal(1,"common reset did not clear board and synchronized pipeline control");
            reset_checks=reset_checks+1;
            reset_n=1;ticks(4);
            // Unit-test acceleration of the fixed 20-bit power-on wait only.
            // The actual registered reset release and all warmup cycles execute.
            force dut.power_count=20'hfffff;
            ticks(3);release dut.power_count;ticks(8);
            if(dut.global_reset_n!==1 || rstn_out!==1 || dut.pipeline_reset_n!==0)
                $fatal(1,"registered power-on release did not retain pipeline in warmup");
        end
    endtask
    task await_release;
        integer n;
        begin
            n=0;
            while(!dut.pipeline_release && n<WAIT_CYCLES+64)begin ticks(1);n=n+1;end
            if(dut.pipeline_release!==1 || dut.board_failed!==0)
                $fatal(1,"healthy camera pipeline failed to release");
            ticks(8);
            if(!dut.system.capture_admit || !dut.system.scan_enable || dut.system.external_fault)
                $fatal(1,"healthy release did not admit capture and scan");
        end
    endtask
    task expect_blocked(input integer label_id);
        begin
            ticks(WAIT_CYCLES+32);
            if(dut.pipeline_reset_n!==0 || dut.pipeline_release!==0 || dut.board_failed!==0)
                $fatal(1,"startup dependency %0d did not hold warmup without false fault",label_id);
            startup_cases=startup_cases+1;
        end
    endtask
    task expect_fault(input [7:0] expected,input integer released);
        begin
            ticks(24);
            if(dut.board_failed!==1 || dut.board_fault!==expected || led[7]!==1 ||
               dut.pipeline_reset_n!==released[0] || dut.pipeline_release!==released[0])
                $fatal(1,"fault %02x not latched with expected reset %0d: got %02x reset %b",
                    expected,released,dut.board_fault,dut.pipeline_reset_n);
            if(released && (!dut.system.external_fault || dut.system.capture_admit ||
               dut.system.scan_enable || dut.system.external_fault_code!==expected))
                $fatal(1,"runtime fault %02x did not stop admission through CDC",expected);
            healthy();ticks(64);
            if(dut.board_failed!==1 || dut.board_fault!==expected ||
               dut.pipeline_reset_n!==released[0] || dut.pipeline_release!==released[0])
                $fatal(1,"fault %02x was not sticky after status recovery",expected);
            if(released && (dut.system.capture_admit || dut.system.scan_enable))
                $fatal(1,"fault recovery silently restarted admission");
        end
    endtask

    integer case_id,summary;
    reg [7:0] expected_fault;
    initial begin
        #7;
        if(dut.camera_configuration.DYNAMIC_PAD_MASK!=1 ||
           dut.camera_configuration.trial_pad_mask!==16'h7ff0 ||
           dut.camera_configuration.RESET_CYCLES!=270000 ||
           dut.camera_configuration.WAIT_CYCLES!=1350000 ||
           dut.camera_configuration.MS_CYCLES!=27000 ||
           dut.camera_configuration.I2C_QUARTER_CYCLES!=68 ||
           dut.camera_configuration.I2C_TIMEOUT_CYCLES!=1350000 ||
           dut.camera_configuration.CHECK_WRITES!=1)
            $fatal(1,"camera control parameters differ from 27MHz CAM2 contract");
        if(dut.system.WIDTH!=640 || dut.system.HEIGHT!=480 ||
           dut.system.OUTPUT_WIDTH!=1920 || dut.system.OUTPUT_HEIGHT!=1080 ||
           dut.system.VSYNC_ACTIVE_HIGH!=0 || dut.system.HREF_ACTIVE_HIGH!=0 ||
           dut.system.HIGH_BYTE_FIRST!=0 || dut.system.BANK_STRIDE!=1048576 ||
           dut.system.cfg_k1!==0 || dut.system.cfg_k2!==0 || dut.system.cfg_k3!==0 ||
           dut.system.cfg_p1!==0 || dut.system.cfg_p2!==0)
            $fatal(1,"camera ingress, geometry or centered 1080 output contract differs");
        for(case_id=1;case_id<=5;case_id=case_id+1)begin
            common_reset();
            case(case_id)
                1:dut.camera_configuration.test_ready=0;
                2:dut.u_ddr3_test_h.test_init_done=0;
                3:dut.u_ddr3_test_h.test_pll_lock=0;
                4:dut.video_pll.test_lock=0;
                5:dut.hdmi_configuration.test_ready=0;
            endcase
            expect_blocked(case_id);
        end
        common_reset();dut.camera_configuration.test_failed=1;
        dut.camera_configuration.test_error=8'h43;
        expect_fault(8'ha8,0);ticks(WAIT_CYCLES+8);
        if(dut.pipeline_release)$fatal(1,"recovered startup sensor error released without reset");
        startup_cases=startup_cases+1;
        common_reset();dut.hdmi_configuration.test_error=4'h2;
        expect_fault(8'ha7,0);startup_cases=startup_cases+1;
        common_reset();dut.camera_configuration.test_failed=1;
        dut.hdmi_configuration.test_error=4'h2;
        expect_fault(8'ha8,0);startup_cases=startup_cases+1;

        common_reset();ticks(WAIT_CYCLES/2);
        dut.camera_configuration.test_ready=0;ticks(5);
        if(dut.sensor_warmup.count!==0)$fatal(1,"readiness chatter retained warmup count");
        dut.camera_configuration.test_ready=1;ticks(WAIT_CYCLES-1);
        if(dut.pipeline_release)$fatal(1,"readiness chatter shortened required interval");
        await_release();chatter_checks=chatter_checks+1;
        if(led[7:1]!==7'b0001111)$fatal(1,"healthy status LED map differs");
        dut.system.test_captured_frames=16;ticks(4);
        if(led[7:1]!==7'b0011111)$fatal(1,"capture progress LED5 mapping differs");
        dut.system.test_processed_frames=16;ticks(4);
        if(led[7:1]!==7'b0111111)$fatal(1,"processing progress LED6 mapping differs");
        dut.system.test_captured_frames=32;dut.system.test_processed_frames=32;ticks(4);
        if(led[7:1]!==7'b0001111)$fatal(1,"progress LEDs do not follow synchronized bit4");
        led_checks=4;

        for(case_id=1;case_id<=7;case_id=case_id+1)begin
            common_reset();await_release();
            case(case_id)
                1:begin dut.camera_configuration.test_ready=0;expected_fault=8'ha9;end
                2:begin dut.camera_configuration.test_failed=1;expected_fault=8'ha8;end
                3:begin dut.u_ddr3_test_h.test_init_done=0;expected_fault=8'ha3;end
                4:begin dut.video_pll.test_lock=0;expected_fault=8'ha4;end
                5:begin dut.hdmi_configuration.test_ready=0;expected_fault=8'ha5;end
                6:begin dut.hdmi_configuration.test_error=4'h1;expected_fault=8'ha7;end
                7:begin dut.system.test_failed=1;dut.system.test_fault=8'h63;expected_fault=8'ha6;end
            endcase
            expect_fault(expected_fault,1);runtime_cases=runtime_cases+1;
        end
        common_reset();await_release();ticks(8);
        if(dut.board_fault!==0 || dut.board_failed || !dut.system.capture_admit)
            $fatal(1,"manual reset did not recover faulted pipeline");
        summary=$fopen("summary.json","w");
        if(summary==0)$fatal(1,"cannot create summary");
        $fwrite(summary,"{\"Passed\":true,\"StartupCases\":%0d,\"RuntimeCases\":%0d,\"ResetChecks\":%0d,\"ReleaseEvents\":%0d,\"LEDChecks\":%0d,\"ChatterChecks\":%0d,\"WarmupCycles\":%0d,\"ReferenceClockHz\":27000000,\"PowerDelayAccelerated\":true}\n",
            startup_cases,runtime_cases,reset_checks,release_events,led_checks,chatter_checks,WAIT_CYCLES);
        $fclose(summary);
        $display("CAMERA_VGA_CONTROL_PASS startup=%0d runtime=%0d release=%0d resets=%0d",startup_cases,runtime_cases,release_events,reset_checks);
        $finish;
    end
    initial begin #(64'd200000000000);$fatal(1,"camera board-control simulation timeout");end
endmodule
