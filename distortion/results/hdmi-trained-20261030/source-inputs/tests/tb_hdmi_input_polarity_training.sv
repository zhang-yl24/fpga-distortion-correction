`timescale 1ns/1ps
// Fast directed training checks. No force or edits of source-domain state.
module tb_hdmi_input_polarity_training;
    localparam W=8,H=3,HT=16,VT=8;
    reg ref_clk=0,pix_clk=0,pix_run=1,rst_n=0,de=0,vs=0,hs=0;
    always #18.5 ref_clk=~ref_clk;
    always #7 if(pix_run)pix_clk=~pix_clk;
    wire known,vi,hi,qualified,failed;
    wire [7:0] fault;
    hdmi1080_input_status_trained #(.WIDTH(W),.HEIGHT(H),.HTOTAL(HT),.VTOTAL(VT),
        .ACTIVITY_REF_CYCLES(50),.PCLK_WINDOW_MIN(120),.PCLK_WINDOW_MAX(145)) dut(
        .ref_clk(ref_clk),.pix_clk(pix_clk),.rst_n(rst_n),.pix_vs(vs),.pix_hs(hs),.pix_de(de),
        .normalized_vs(),.qualified(qualified),.failed(failed),.fault(fault),
        .polarity_known_ref(known),.vs_inactive_ref(vi),.hs_inactive_ref(hi),
        .good_frames(),.bad_frames(),.pclk_edges_per_window(),.last_pixels_per_line(),.last_lines());
    integer cases=0,total_ref=0;
    always @(posedge ref_clk)begin
        total_ref=total_ref+1;
        if(total_ref>50000)$fatal(1,"bounded training test timeout");
        if(!known && qualified)$fatal(1,"untrained observer qualified");
    end
    task automatic reset_common;
        begin
            @(negedge ref_clk);rst_n=0;pix_run=1;de=0;vs=0;hs=0;
            repeat(12)@(negedge ref_clk);rst_n=1;repeat(20)@(negedge ref_clk);
            if(known || failed || fault || dut.polarity_known || dut.candidate_valid || dut.training_line_active)
                $fatal(1,"reset retained training/polarity/fault");
        end
    endtask
    // glitch: 0 none, 1 first sample flips both, 2 middle HS, 3 middle VS.
    task automatic line(input integer pixels,input integer inactive,input integer glitch);
        integer i;
        begin
            for(i=0;i<pixels;i=i+1)begin
                @(negedge pix_clk);de=1;vs=inactive;hs=inactive;
                if(glitch==1 && i==0)begin vs=!inactive;hs=!inactive;end
                if(glitch==2 && i==3)hs=!inactive;
                if(glitch==3 && i==3)vs=!inactive;
            end
            @(negedge pix_clk);de=0;vs=inactive;hs=inactive;
            repeat(5)@(negedge ref_clk);
        end
    endtask
    task automatic expect_unknown;
        begin
            if(known || dut.polarity_known || qualified)$fatal(1,"invalid or single line learned polarity");
        end
    endtask
    task automatic expect_known(input integer inactive);
        begin
            if(!known || vi!==inactive[0] || hi!==inactive[0] ||
               !dut.polarity_known || dut.vs_inactive!==inactive[0] || dut.hs_inactive!==inactive[0])
                $fatal(1,"two matching valid lines did not train expected polarity");
        end
    endtask
    task automatic pass(input string name);
        begin cases=cases+1;$display("POLARITY_TRAINING_CASE %s PASS",name);end
    endtask
    integer bad_kind;
    initial begin
        reset_common();line(W,0,0);expect_unknown();line(W,0,0);expect_known(0);pass("two_positive_lines");
        reset_common();line(W,1,0);expect_unknown();line(W,1,0);expect_known(1);pass("two_negative_lines");

        reset_common();line(W,0,1);expect_unknown();line(W,0,0);expect_unknown();
        line(W,0,0);expect_known(0);pass("first_de_single_sample_conflict_retrains");

        reset_common();line(W,0,0);expect_unknown();line(W-1,0,0);expect_unknown();
        line(W,0,0);expect_unknown();line(W,0,0);expect_known(0);pass("short_line_restarts_consecutive_evidence");

        reset_common();line(W,0,0);expect_unknown();line(W+1,0,0);expect_unknown();
        line(W,0,0);expect_unknown();line(W,0,0);expect_known(0);pass("long_line_restarts_consecutive_evidence");

        reset_common();line(W,0,0);line(W,0,2);expect_unknown();
        line(W,0,0);expect_unknown();line(W,0,0);expect_known(0);pass("changing_hs_restarts_training");

        reset_common();line(W,0,0);line(W,0,3);expect_unknown();
        line(W,0,0);expect_unknown();line(W,0,0);expect_known(0);pass("changing_vs_restarts_training");

        reset_common();line(W,0,0);line(W,1,0);expect_unknown();
        line(W,1,0);expect_known(1);pass("different_stable_candidate_restarts_pair");

        reset_common();line(W,0,0);expect_unknown();
        @(negedge pix_clk);#1;pix_run=0;repeat(100)@(negedge ref_clk);expect_unknown();
        pix_run=1;line(W,0,0);expect_known(0);pass("clock_stop_does_not_invent_second_line");

        for(bad_kind=2;bad_kind<=3;bad_kind=bad_kind+1)begin
            reset_common();line(W,0,0);line(W,0,0);expect_known(0);
            line(W,0,bad_kind);repeat(10)@(negedge ref_clk);
            if(!failed || dut.timing_fault!==8'h21)$fatal(1,"post-lock sync conflict lost strict failure");
            line(W,1,0);line(W,1,0);repeat(10)@(negedge ref_clk);
            if(!failed || !known || vi || hi || dut.timing_fault!==8'h21)
                $fatal(1,"post-lock fault or polarity self-cleared without reset");
        end
        pass("post_lock_hs_vs_conflict_stays_failed_and_locked");
        reset_common();line(W,1,0);line(W,1,0);expect_known(1);pass("common_reset_allows_new_polarity");
        if(cases!=11)$fatal(1,"training coverage count differs");
        $display("POLARITY_TRAINING_SUMMARY cases=%0d reference_cycles=%0d",cases,total_ref);
        $display("PASS hdmi input polarity training directed regression");
        $finish;
    end
endmodule
