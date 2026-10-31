`timescale 1ps/1ps
// DIGITAL observer unit only: no DDR IP, board primitives or HDMI chip model.
// Two exact1080 raster/polarity phases. No force of internal qualification.
module tb_board1080_input_status_cdc;
    localparam W=1920,H=1080,HT=2200,VT=1125,X0=192,Y0=41;
    reg ref_clk=0,pix_clk=0,rst_n=0,run_pix=1,source_enable=0,reverse_polarity=0;
    integer ref_phase=0,ref_delay,pix_phase=0,pix_delay;
    initial forever begin
        ref_phase=ref_phase+500000;ref_delay=ref_phase/27;ref_phase=ref_phase%27;
        #(ref_delay)ref_clk=~ref_clk;
    end
    initial begin
        #1777;
        forever begin
            pix_phase=pix_phase+2000000;pix_delay=pix_phase/297;pix_phase=pix_phase%297;
            #(pix_delay)if(run_pix)pix_clk=~pix_clk;
        end
    end
    reg pix_vs=0,pix_hs=0,pix_de=0;
    integer src_x=0,src_y=0,active_width=W;
    integer complete_rasters=0;
    always @(negedge pix_clk)begin
        if(!rst_n || !source_enable)begin
            src_x=0;src_y=0;pix_vs=reverse_polarity;pix_hs=reverse_polarity;pix_de=0;
        end else begin
            pix_vs=(src_y<5)^reverse_polarity;
            pix_hs=(src_x<44)^reverse_polarity;
            pix_de=src_y>=Y0 && src_y<Y0+H && src_x>=X0 && src_x<X0+active_width;
            if(src_x==HT-1)begin
                src_x=0;
                if(src_y==VT-1)begin src_y=0;complete_rasters=complete_rasters+1;end
                else src_y=src_y+1;
            end else src_x=src_x+1;
        end
    end
    wire normalized_vs,qualified,failed,polarity_known,vs_inactive,hs_inactive;
    wire [7:0] fault;wire [31:0] good_frames,bad_frames,pclk_edges;
    wire [15:0] last_pixels,last_lines;
    hdmi1080_input_status_trained dut(.ref_clk(ref_clk),.pix_clk(pix_clk),.rst_n(rst_n),
        .pix_vs(pix_vs),.pix_hs(pix_hs),.pix_de(pix_de),.normalized_vs(normalized_vs),
        .qualified(qualified),.failed(failed),.fault(fault),.polarity_known_ref(polarity_known),
        .vs_inactive_ref(vs_inactive),.hs_inactive_ref(hs_inactive),
        .good_frames(good_frames),.bad_frames(bad_frames),.pclk_edges_per_window(pclk_edges),
        .last_pixels_per_line(last_pixels),.last_lines(last_lines));
    integer total_ref_cycles=0,qualification_phases=0,seen_polarities=0;
    integer cov_early_refusal=0,cov_geometry=0,cov_bad_format=0,cov_stop=0,cov_sticky=0,cov_reset_clear=0,cov_requalify=0;
    always @(posedge ref_clk)begin
        total_ref_cycles=total_ref_cycles+1;
        if(total_ref_cycles>9000000)$fatal(1,"input_status bounded9M reference-cycle timeout");
        if(rst_n)begin
            if(!qualified && good_frames<2)cov_early_refusal=cov_early_refusal+1;
            if(qualified)begin
                if(failed || fault!=0 || !polarity_known || good_frames<2 ||
                   last_pixels!=W || last_lines!=H || pclk_edges<73500 || pclk_edges>75000)
                    $fatal(1,"input_status admitted an incomplete/mismatched geometry or activity window");
                if(vs_inactive!==reverse_polarity || hs_inactive!==reverse_polarity)
                    $fatal(1,"input_status inferred the wrong inactive HS/VS levels");
                cov_geometry=cov_geometry+1;
            end
        end
    end
    task automatic common_reset(input integer polarity);
        begin
            @(negedge ref_clk);rst_n=0;source_enable=0;run_pix=1;reverse_polarity=polarity;active_width=W;
            repeat(16)@(negedge ref_clk);
            rst_n=1;repeat(20)@(negedge ref_clk);
            if(qualified!==1'b0 || failed!==1'b0 || fault!==8'h00 || polarity_known!==1'b0 || good_frames!==0)
                $fatal(1,"input_status common reset retained fault/admission/polarity/frame evidence");
            cov_reset_clear=cov_reset_clear+1;
        end
    endtask
    task automatic await_qualified(input integer polarity);
        integer elapsed;
        begin
            elapsed=0;
            while(qualified!==1'b1 && elapsed<3500000)begin @(negedge ref_clk);elapsed=elapsed+1;end
            if(qualified!==1'b1 || failed || vs_inactive!==polarity[0] || hs_inactive!==polarity[0])
                $fatal(1,"input_status exact1080/30 nominal raster did not qualify polarity%0d fault%h",polarity,fault);
            qualification_phases=qualification_phases+1;seen_polarities=seen_polarities|(1<<polarity);
        end
    endtask
    // A snapshot is consumed from the NEW reference register, never by
    // combinational use of the asynchronous held source bus.
    reg [104:0] expected_snapshot;
    integer snapshot_applications=0;
    always @(posedge ref_clk) begin
        if(dut.geometry.r_run && dut.geometry.snapshot_apply)begin
            expected_snapshot=dut.geometry.ref_snapshot;
            #1;
            if({good_frames,bad_frames,last_lines,last_pixels,
                dut.geometry.held_fault,dut.geometry.held_healthy}!==expected_snapshot)
                $fatal(1,"reference snapshot application was not atomic");
            snapshot_applications=snapshot_applications+1;
        end
    end
    integer elapsed,result_file;
    initial begin
        common_reset(0);@(negedge ref_clk);source_enable=1;
        await_qualified(0);
        $display("PASS input_status: exact2200x1125/1920x1080 normalized positive sync, two-good-frame admission");

        // Change only active width. HS/VS totals, clocks and all other source
        //timing remain exact, so expected fault12 proves the short-DE-line path.
        @(negedge pix_clk);#1;active_width=W-1;
        elapsed=0;
        while(fault!==8'h12 && elapsed<81000)begin @(negedge ref_clk);elapsed=elapsed+1;end
        if(failed!==1'b1 || qualified!==1'b0 || fault!==8'h12)
            $fatal(1,"input_status changed1919-pixel format was not rejected by the short-line fault");
        cov_bad_format=cov_bad_format+1;
        @(negedge pix_clk);#1;active_width=W;
        repeat(1000)@(negedge ref_clk);
        if(!failed || qualified)$fatal(1,"input_status format fault self-cleared without common reset");
        cov_sticky=cov_sticky+1;
        $display("PASS input_status: changed-format short line rejects admission and stays failed");

        common_reset(1);@(negedge ref_clk);source_enable=1;
        await_qualified(1);cov_requalify=cov_requalify+1;
        $display("PASS input_status: common reset clears format fault; inverted HS/VS requalifies exact1080 mode");

        // Stop only PCLK at a falling edge. Reference clock keeps running and
        //must revoke admission; no fabricated pixel/toggle response is supplied.
        @(negedge pix_clk);#1;run_pix=0;
        elapsed=0;
        while(failed!==1'b1 && elapsed<54000)begin @(negedge ref_clk);elapsed=elapsed+1;end
        if(failed!==1'b1 || qualified!==1'b0 || (fault!==8'h25 && fault!==8'hc0))
            $fatal(1,"input_status stopped PCLK not rejected by reference activity watchdog fault%h",fault);
        cov_stop=cov_stop+1;
        @(negedge ref_clk);run_pix=1;
        repeat(1000)@(negedge ref_clk);
        if(!failed || qualified)$fatal(1,"input_status stopped-clock fault self-cleared when clock returned");
        cov_sticky=cov_sticky+1;
        $display("PASS input_status: stopped PCLK revoked admission while reference ran, fault remained sticky");

        common_reset(0);
        if(snapshot_applications<3 || qualification_phases!=2 || seen_polarities!=3 || complete_rasters<6 || cov_early_refusal==0 ||
           cov_geometry==0 || cov_bad_format!=1 || cov_stop!=1 || cov_sticky!=2 || cov_reset_clear!=3 || cov_requalify!=1)
            $fatal(1,"input_status unit coverage vacuous");
        $display("INPUT_STATUS_COVERAGE qualified_phases=%0d polarity_mask=%0d complete_rasters=%0d early_refusal=%0d geometry=%0d changed_format=%0d stopped_pclk=%0d sticky=%0d resets=%0d requalified=%0d",
            qualification_phases,seen_polarities,complete_rasters,cov_early_refusal,cov_geometry,
            cov_bad_format,cov_stop,cov_sticky,cov_reset_clear,cov_requalify);
        result_file=$fopen("input-status-cdc-unit-summary.json","w");
        $fdisplay(result_file,"{\"passed\":true,\"qualification_phases\":2,\"polarity_mask\":3,\"complete_rasters\":%0d,\"changed_format\":1,\"stopped_pclk\":1,\"sticky_checks\":2,\"common_reset_checks\":3,\"reset_requalified\":1,\"reference_cycles\":%0d,\"DDRIPElaborated\":false,\"HardwareVerified\":false}",complete_rasters,total_ref_cycles);
        $fclose(result_file);
        $display("PASS board1080 input_status_cdc unit: digital geometry/polarity/admission/fault/reset only; no physical AC/HDMI lock/RGB/DDRIP/STA evidence");
        $finish;
    end
endmodule

`timescale 1ns/1ps
// Fast directed enable/epoch regression, independent of the native raster TB.
// No force of mailbox contents or admission predicates; stop only source clock.
module tb_dvp_mode_admission_monitor_cdc_small;
    reg ref_clk=0,pclk=0,pclk_run=1,rst_n=0,enable=0,vs=0,href=0;
    always #18.5 ref_clk=~ref_clk;
    always #7 if(pclk_run)pclk=~pclk;
    wire authorize,failed;wire [7:0] fault;
    wire [31:0] good,bad,edges;wire [15:0] lines,bytes_last;
    wire pf,vf,hf,ff,sf;
    dvp_mode_admission_monitor_cdc #(.BYTES_PER_LINE(8),.LINES_PER_FRAME(3),
        .ACTIVITY_WINDOW_REF_CYCLES(50),.SNAPSHOT_INTERVAL_REF_CYCLES(17),
        .STARTUP_REF_CYCLES(5000),.MAX_PCLK_IDLE_REF_CYCLES(200),
        .MAX_VSYNC_IDLE_REF_CYCLES(4000),.MAX_HREF_IDLE_REF_CYCLES(4000),
        .MAX_FRAME_IDLE_REF_CYCLES(4000),.MAX_SNAPSHOT_IDLE_REF_CYCLES(2000)) dut(
        .ref_clk(ref_clk),.pclk(pclk),.rst_n(rst_n),.enable(enable),.vsync_active(vs),.href_active(href),
        .raw_authorize(authorize),.failed(failed),.fault(fault),.good_frames(good),.bad_frames(bad),
        .pclk_edges_per_window(edges),.last_frame_lines(lines),.last_line_bytes(bytes_last),
        .pclk_fresh(pf),.vsync_fresh(vf),.href_fresh(hf),.frame_fresh(ff),.snapshot_fresh(sf));
    integer cases=0,applications=0,source_snapshots=0,gray_checks=0;
    reg prev_run=0,prev_ack=0;reg [31:0] prev_gray=0,gray_difference;
    reg [104:0] prev_held=0,expected_snapshot;
    always @(negedge pclk) begin
        if(dut.p_run && prev_run)begin
            gray_difference=dut.edge_gray^prev_gray;
            if((gray_difference&(gray_difference-1))!=0)
                $fatal(1,"source Gray changed multiple bits while enabled");
            if(dut.snapshot_ack==prev_ack && dut.held_snapshot!==prev_held)
                $fatal(1,"held source bus changed without an acknowledgement");
            if(dut.snapshot_ack!=prev_ack)source_snapshots=source_snapshots+1;
            gray_checks=gray_checks+1;
        end
        prev_run=dut.p_run;prev_gray=dut.edge_gray;prev_ack=dut.snapshot_ack;prev_held=dut.held_snapshot;
    end
    always @(posedge ref_clk)begin
        if(dut.r_run && dut.snapshot_apply)begin
            expected_snapshot=dut.ref_snapshot;
            #1;
            if({good,bad,lines,bytes_last,dut.held_fault,dut.held_healthy}!==expected_snapshot)
                $fatal(1,"small monitor did not apply one atomic ref snapshot");
            applications=applications+1;
        end
    end
    task automatic mark(input string name);
        begin cases=cases+1;$display("HDMI_INPUT_CDC_CASE %s PASS",name);end
    endtask
    task automatic boundary;
        begin @(negedge pclk);vs=1;href=0;repeat(3)@(negedge pclk);vs=0;repeat(3)@(negedge pclk);end
    endtask
    task automatic line_data(input integer count);
        begin @(negedge pclk);href=1;repeat(count)@(negedge pclk);href=0;repeat(3)@(negedge pclk);end
    endtask
    task automatic one_frame;
        begin boundary();repeat(3)line_data(8);boundary();end
    endtask
    task automatic await_good;
        integer limit;
        begin
            limit=0;
            while(!authorize && limit<500)begin @(negedge ref_clk);limit=limit+1;end
            if(!authorize || failed || good!=1 || bad!=0 || lines!=3 || bytes_last!=8 ||
               !(pf&&vf&&hf&&ff&&sf))
                $fatal(1,"new epoch frame not admitted: good=%0d bad=%0d fault=%h",good,bad,fault);
        end
    endtask
    task automatic disable_both;
        begin
            @(negedge ref_clk);enable=0;vs=0;href=0;
            repeat(14)@(negedge ref_clk);
            if(authorize || good || bad || failed || dut.r_run || dut.p_run)
                $fatal(1,"disable did not clear both running epochs");
        end
    endtask
    task automatic enable_fresh;
        begin
            @(negedge ref_clk);enable=1;
            repeat(30)@(negedge ref_clk);
            if(!dut.r_run || authorize || good || bad || failed)
                $fatal(1,"enable imported old frame or failed to arm fresh epoch");
        end
    endtask
    initial begin
        repeat(8)@(negedge ref_clk);rst_n=1;
        repeat(10)@(negedge ref_clk);
        enable_fresh();one_frame();await_good();
        mark("atomic_held_snapshot_gray_and_first_new_frame");

        // Arrange disable while a real request is outstanding. Both domains
        // must discard the old request and held metadata before a new epoch.
        wait(dut.snapshot_request!=dut.ack_seen);
        disable_both();enable_fresh();
        repeat(50)@(negedge ref_clk);
        if(authorize || good || bad) $fatal(1,"old in-flight snapshot resurfaced after re-enable");
        one_frame();await_good();
        mark("enable_restart_discards_pending_old_snapshot");

        // If PCLK does not observe a low enable, re-enable must stay closed.
        @(negedge pclk);#1;pclk_run=0;
        @(negedge ref_clk);enable=0;repeat(12)@(negedge ref_clk);
        enable=1;repeat(40)@(negedge ref_clk);
        if(authorize || good || bad || dut.r_run || dut.enable_epoch_ready)
            $fatal(1,"stopped source reused old epoch after unobserved enable pulse");
        pclk_run=1;repeat(25)@(negedge ref_clk);
        if(authorize || dut.r_run) $fatal(1,"unobserved disable was silently accepted on clock restart");
        disable_both();enable_fresh();one_frame();await_good();
        mark("stopped_clock_enable_requires_observed_source_disable");

        // Reset while PCLK is stopped: only local reset synchronizers assert
        // asynchronously. Their validity masks must prevent old source data
        // from being accepted by the running reference domain.
        @(negedge pclk);#1;pclk_run=0;
        @(negedge ref_clk);rst_n=0;
        repeat(8)@(negedge ref_clk);rst_n=1;
        repeat(45)@(negedge ref_clk);
        if(authorize || good || bad || failed || dut.r_run)
            $fatal(1,"common reset with stopped PCLK leaked synchronous source state");
        pclk_run=1;repeat(35)@(negedge ref_clk);
        if(authorize || good || bad || !dut.r_run)
            $fatal(1,"post-reset source failed fresh rearm");
        one_frame();await_good();
        mark("common_reset_while_pclk_stopped_has_no_old_epoch");

        disable_both();enable_fresh();boundary();line_data(7);boundary();
        repeat(100)@(negedge ref_clk);
        if(authorize || !failed || fault!=8'h12)
            $fatal(1,"registered source fault lost original short-line code=%h",fault);
        repeat(20)@(negedge ref_clk);
        if(!failed || fault!=8'h12) $fatal(1,"source fault unexpectedly cleared");
        disable_both();enable_fresh();one_frame();await_good();
        mark("source_fault_code_sticky_and_enable_recovery");

        if(cases!=5 || applications<8 || source_snapshots<8 || gray_checks<100)
            $fatal(1,"small CDC coverage vacuous");
        $display("HDMI_INPUT_CDC_SMALL_SUMMARY cases=%0d applications=%0d source_snapshots=%0d gray_checks=%0d",
            cases,applications,source_snapshots,gray_checks);
        $display("PASS hdmi_input_cdc small");$finish;
    end
    initial begin #2000000;$fatal(1,"small CDC bounded timeout");end
endmodule
