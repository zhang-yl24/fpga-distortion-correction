`timescale 1ps/1ps
// Models the real System's registered debug commit, not a combinational accept.
// This verifies only the new same-core control; real bank snapshots have separate evidence.
module tb_frame_ab_control;
    reg clk=0;always #4000 clk=~clk;
    reg rst_n=0,failed=0,src_valid=0,src_ready=0;
    reg commit_debug=0;wire correction_enable;
    frame_ab_control dut(.clk(clk),.rst_n(rst_n),.commit_pulse(commit_debug),.failed(failed),.correction_enable(correction_enable));
    integer ticks=0,accepted=0,checked=0,held_offer_cycles=0,fault_hold_cycles=0,cancelled=0,summary;
    reg captured_mode=0,model_next=0;
    always @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin commit_debug<=0;captured_mode<=0;end
        else begin
            commit_debug<=src_valid&&src_ready;
            if(src_valid&&src_ready)begin
                if(commit_debug)$fatal(1,"fixture violates bank no-back-to-back accepted frame contract");
                captured_mode<=correction_enable;accepted=accepted+1;
            end
        end
    end
    always @(posedge clk)begin
        ticks=ticks+1;if(ticks>1000)$fatal(1,"bounded control admission");
        if(!rst_n)model_next=0;
        else if(!failed&&commit_debug)model_next=!model_next;
        #1;if(correction_enable!==model_next)$fatal(1,"control differs from registered-debug/fault-priority model");
    end
    task automatic reset_epoch;
        begin
            @(negedge clk);src_valid=0;src_ready=0;failed=0;rst_n=0;
            #1000;if(correction_enable!==0)$fatal(1,"asynchronous reset must assert raw immediately");
            repeat(3)@(negedge clk);rst_n=1;
            repeat(3)@(negedge clk);
        end
    endtask
    task automatic frame(input bit wanted,input integer held);
        integer j;begin
            @(negedge clk);src_valid=1;src_ready=0;
            for(j=0;j<held;j=j+1)begin
                @(posedge clk);#1;
                if(correction_enable!==wanted||commit_debug)$fatal(1,"offered/unaccepted frame advanced mode");
                held_offer_cycles=held_offer_cycles+1;@(negedge clk);
            end
            src_ready=1;@(posedge clk);#1;
            if(captured_mode!==wanted||correction_enable!==wanted||commit_debug!==1)$fatal(1,"mode changed at source-accept edge");
            @(negedge clk);src_valid=0;src_ready=0;
            @(posedge clk);#1;
            if(correction_enable!==!wanted||commit_debug!==0)$fatal(1,"next-frame mode did not change on following debug edge");
            checked=checked+1;repeat(3)@(negedge clk);
        end
    endtask
    initial begin
        reset_epoch();frame(0,5);frame(1,3);frame(0,1);frame(1,0);
        // A runtime fault freezes the controller, including a pending debug event.
        reset_epoch();@(negedge clk);src_valid=1;src_ready=1;
        @(posedge clk);#1;if(captured_mode!==0||commit_debug!==1)$fatal(1,"fault setup frame missing");
        @(negedge clk);src_valid=0;src_ready=0;failed=1;
        repeat(5)begin @(posedge clk);#1;if(correction_enable!==0)$fatal(1,"fault must hold mode, not locally reset/restart datapath");fault_hold_cycles=fault_hold_cycles+1;end
        // Only a common epoch reset re-arms; it cancels pending debug consumption.
        reset_epoch();frame(0,2);
        @(negedge clk);src_valid=1;src_ready=1;
        @(posedge clk);#1;if(captured_mode!==1||commit_debug!==1)$fatal(1,"reset-boundary setup missing");
        #1000;rst_n=0;src_valid=0;src_ready=0;
        #1;if(correction_enable!==0||commit_debug!==0)$fatal(1,"reset did not cancel pending event");
        cancelled=cancelled+1;repeat(3)@(negedge clk);rst_n=1;repeat(3)@(negedge clk);frame(0,4);
        if(checked!=6||held_offer_cycles!=15||fault_hold_cycles!=5||cancelled!=1)$fatal(1,"control coverage counts");
        summary=$fopen("summary.json","w");
        $fdisplay(summary,"{\"passed\":true,\"checked_frames\":%0d,\"accepted_model_events\":%0d,\"held_offer_cycles\":%0d,\"fault_hold_cycles\":%0d,\"cancelled_pending_commit\":%0d,\"cycles\":%0d}",checked,accepted,held_offer_cycles,fault_hold_cycles,cancelled,ticks);$fclose(summary);
        $display("PASS FRAME_AB_CONTROL: registeredcommit raw/corrected nextframe, stalledoffer, stickyfault, commonreset cancellation checked=%0d",checked);$finish;
    end
endmodule
