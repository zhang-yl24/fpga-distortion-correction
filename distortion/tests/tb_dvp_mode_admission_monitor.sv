`timescale 1ns/1ps
// Nominal asynchronous42MHz PCLK /27MHz reference; no vendor IP or device.
module tb_dvp_mode_admission_monitor;
    reg ref_clk=0,pclk=0,pclk_run=1,rst_n=0,enable=0,vs=0,href=0;
    always #18.519 ref_clk=~ref_clk;
    always #11.905 if(pclk_run)pclk=~pclk;
    wire authorize,failed;wire [7:0] fault;
    wire [31:0] good,bad,edges;wire [15:0] lines,bytes_last;
    wire pf,vf,hf,ff,sf;
    dvp_mode_admission_monitor #(.ACTIVITY_WINDOW_REF_CYCLES(270),
        .SNAPSHOT_INTERVAL_REF_CYCLES(270),.STARTUP_REF_CYCLES(2000000),
        .MAX_PCLK_IDLE_REF_CYCLES(1000),.MAX_VSYNC_IDLE_REF_CYCLES(2000000),
        .MAX_HREF_IDLE_REF_CYCLES(4000),.MAX_FRAME_IDLE_REF_CYCLES(2000000),
        .MAX_SNAPSHOT_IDLE_REF_CYCLES(2700)) dut(
        .ref_clk(ref_clk),.pclk(pclk),.rst_n(rst_n),.enable(enable),.vsync_active(vs),.href_active(href),
        .raw_authorize(authorize),.failed(failed),.fault(fault),.good_frames(good),.bad_frames(bad),
        .pclk_edges_per_window(edges),.last_frame_lines(lines),.last_line_bytes(bytes_last),
        .pclk_fresh(pf),.vsync_fresh(vf),.href_fresh(hf),.frame_fresh(ff),.snapshot_fresh(sf));
    integer test_count=0;
    reg [31:0] previous_gray=0;reg [104:0] previous_held=0;reg previous_ack=0;
    reg [31:0] gray_difference;
    always @(negedge pclk)begin
        if(dut.p_reset[1])begin
            gray_difference=dut.edge_gray^previous_gray;
            if((gray_difference & (gray_difference-1))!=0)$fatal(1,"Registered PCLK Gray changed multiple bits");
            if(dut.snapshot_ack==previous_ack && dut.held_snapshot!==previous_held)
                $fatal(1,"Held snapshot changed without an acknowledgement event");
        end
        previous_gray=dut.edge_gray;previous_held=dut.held_snapshot;previous_ack=dut.snapshot_ack;
    end
    task reset_monitor;
        begin
            enable=0;rst_n=0;vs=0;href=0;pclk_run=1;
            repeat(8)@(negedge ref_clk);rst_n=1;enable=1;
            repeat(8)@(negedge pclk);repeat(8)@(negedge ref_clk);
            if(authorize || good || failed)$fatal(1,"Old/reset snapshot admitted without a full new frame");
        end
    endtask
    task frame_boundary;
        begin @(negedge pclk);vs=1;href=0;repeat(3)@(negedge pclk);vs=0;repeat(3)@(negedge pclk);end
    endtask
    task line_bytes(input integer n);
        begin @(negedge pclk);href=1;repeat(n)@(negedge pclk);href=0;repeat(3)@(negedge pclk);end
    endtask
    task complete_720_frame;
        begin frame_boundary();for(integer y=0;y<720;y=y+1)line_bytes(2560);frame_boundary();end
    endtask
    task wait_good;
        integer timeout;
        begin
            timeout=0;while(!authorize && timeout<1000)begin @(negedge ref_clk);timeout=timeout+1;end
            if(!authorize || failed || good!=1 || bad!=0 || lines!=720 || bytes_last!=2560)
                $fatal(1,"Full720 frame not authorized fault=%h good=%d bad=%d lines=%d bytes=%d",fault,good,bad,lines,bytes_last);
            if(!(pf&&vf&&hf&&ff&&sf) || edges<418 || edges>422)$fatal(1,"Gray edge rate/freshness differs edges=%d",edges);
        end
    endtask
    task expect_fault(input [7:0] expected);
        begin
            repeat(700)@(negedge ref_clk);
            if(authorize || !failed || fault!==expected)$fatal(1,"Expected fault%h actual%h authorize%b",expected,fault,authorize);
            test_count=test_count+1;
        end
    endtask
    initial begin
        reset_monitor();repeat(500)@(negedge ref_clk);
        if(authorize || good)$fatal(1,"PCLK activity alone authorized RAW");
        complete_720_frame();wait_good();test_count=test_count+1;
        $display("PASS full RGB5651280x720:720lines x2560bytes, Gray PCLK42/27 activity and held atomic metadata");
        // Clock still runs but HREF/frames stop. The watchdog is in ref_clk.
        repeat(4200)@(negedge ref_clk);
        if(authorize || !failed || fault!=8'hc2)$fatal(1,"Missing HREF did not revoke admission fault%h",fault);
        test_count=test_count+1;
        // A later source edge does not clear a latched timeout.
        frame_boundary();repeat(500)@(negedge ref_clk);
        if(authorize || !failed)$fatal(1,"Stale session silently reauthorized");
        reset_monitor();complete_720_frame();wait_good();
        @(negedge pclk);pclk_run=0;
        repeat(1200)@(negedge ref_clk);
        if(authorize || !failed || fault!=8'hc0)$fatal(1,"PCLK clockstop left RAW authorized fault%h",fault);
        test_count=test_count+1;
        // Reset/enable must assert even when the PCLK domain cannot run.
        enable=0;repeat(5)@(negedge ref_clk);
        if(authorize || good || bad)$fatal(1,"Disable retained old held frame");
        reset_monitor();frame_boundary();line_bytes(2559);frame_boundary();expect_fault(8'h12);
        reset_monitor();frame_boundary();line_bytes(2561);frame_boundary();expect_fault(8'h11);
        reset_monitor();frame_boundary();line_bytes(2560);frame_boundary();expect_fault(8'h13);
        reset_monitor();frame_boundary();@(negedge pclk);href=1;repeat(7)@(negedge pclk);vs=1;
        repeat(3)@(negedge pclk);href=0;vs=0;expect_fault(8'h14);
        reset_monitor();@(negedge pclk);vs=1;repeat(3)@(negedge pclk);href=1;repeat(4)@(negedge pclk);
        href=0;vs=0;expect_fault(8'h15);
        $display("PASS DVP admission directed regression:%0dchecks, short odd/long lines, missing frame lines, truncated line, HREF during VSYNC, clockstop, HREF stale and reset epoch",test_count);
        $finish;
    end
    initial begin #180000000;$fatal(1,"DVP monitor simulation timeout");end
endmodule
