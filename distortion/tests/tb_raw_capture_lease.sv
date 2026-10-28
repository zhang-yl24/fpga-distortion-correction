`timescale 1ns/1ps
module tb_raw_capture_lease;
    reg clk=0;always #4 clk=~clk;
    reg rst_n=0,grant_valid=0,stop_request=0,interlock_stop=0,request_valid=0;
    reg [31:0] grant_frames=0,grant_cycles=0;
    reg core_request_ready=0,core_done=0,core_failed=0,core_bank_locked=0;
    wire grant_ready,request_ready,core_request_valid,armed,in_flight,batch_done,grant_accepted,grant_rejected,requires_reset,draining;
    wire [31:0] remaining_frames,remaining_cycles,admitted_frames;wire [3:0] stop_reason;
    raw_capture_lease #(.MAX_FRAMES(3),.MAX_LEASE_CYCLES(100)) dut(.*);
    task reset_all;
        begin @(negedge clk);rst_n=0;grant_valid=0;stop_request=0;interlock_stop=0;request_valid=0;
            core_request_ready=0;core_done=0;core_failed=0;core_bank_locked=0;
            repeat(3)@(negedge clk);rst_n=1;@(negedge clk);end
    endtask
    task grant;
        input [31:0] frames,cycles;
        begin if(!grant_ready)$fatal(1,"grant not ready");grant_frames=frames;grant_cycles=cycles;
            grant_valid=1;@(negedge clk);grant_valid=0;@(negedge clk);end
    endtask
    task complete;
        begin core_done=1;core_bank_locked=0;@(negedge clk);core_done=0;end
    endtask
    initial begin
        reset_all();core_bank_locked=1;grant_frames=1;grant_cycles=100;grant_valid=1;
        @(negedge clk);
        if(!grant_rejected || grant_accepted || armed)$fatal(1,"Busy lease silently dropped/raced a fresh grant");
        grant_valid=0;core_bank_locked=0;@(negedge clk);
        grant_valid=1;stop_request=1;@(negedge clk);
        if(!grant_rejected || grant_accepted || armed)$fatal(1,"STOP did not beat a simultaneous grant");
        grant_valid=0;stop_request=0;@(negedge clk);grant_valid=1;@(negedge clk);
        if(!grant_accepted || grant_rejected || !armed)$fatal(1,"Valid lease omitted actual grant acceptance");
        $display("PASS lease: fresh grant returns actual accepted/rejected feedback, readiness race and simultaneous STOP fail closed.");
        reset_all();grant(2,10);request_valid=1;
        repeat(4)begin @(negedge clk);if(core_request_valid || admitted_frames!=0)$fatal(1,"Backpressured request admitted");end
        core_request_ready=1;@(negedge clk);core_request_ready=0;core_bank_locked=1;
        if(admitted_frames!=1 || !in_flight)$fatal(1,"First admission missing");
        repeat(10)@(negedge clk);
        if(armed || !draining || !core_bank_locked || stop_reason!=2 || core_request_valid)$fatal(1,"Lease expiry did not drain");
        if(grant_ready)$fatal(1,"Lease renewed before old transaction drained");
        complete();@(negedge clk);
        if(!batch_done || !grant_ready || requires_reset)$fatal(1,"Lease batch completion missing");
        $display("PASS lease: host silence expires finite grant, backpressure consumes no frame budget, existing bank drains before renewal.");
        request_valid=0;grant(1,100);request_valid=1;core_request_ready=1;
        @(negedge clk);core_bank_locked=1;
        if(armed || admitted_frames!=1 || stop_reason!=1)$fatal(1,"Frame budget not enforced");
        repeat(4)@(negedge clk);if(core_request_valid)$fatal(1,"Budget overrun");
        request_valid=0;complete();@(negedge clk);
        $display("PASS lease: frame budget stops new admissions while accepted frame remains owned.");
        grant(2,100);interlock_stop=1;@(negedge clk);
        if(armed || stop_reason!=4 || core_request_valid)$fatal(1,"Interlock ignored");
        interlock_stop=0;@(negedge clk);grant(0,100);if(stop_reason!=6 || armed)$fatal(1,"Zero budget admitted");
        grant(1,101);if(stop_reason!=6 || armed)$fatal(1,"Unbounded lease admitted");
        grant(4,100);if(stop_reason!=6 || armed)$fatal(1,"Overlarge budget admitted");
        // Simulate a host command register stuck high after disconnect. It
        // must not silently renew a finite lease when a previous batch ends.
        grant_frames=1;grant_cycles=3;grant_valid=1;repeat(8)@(negedge clk);
        if(armed || grant_ready || admitted_frames!=0 || remaining_cycles!=0)$fatal(1,"Stale grant silently renewed lease");
        grant_valid=0;@(negedge clk);
        if(!grant_ready)$fatal(1,"Fresh grant not re-enabled after low cycle");
        grant(2,100);core_request_ready=1;request_valid=1;@(negedge clk);
        request_valid=0;core_bank_locked=1;core_failed=1;@(negedge clk);
        if(!requires_reset || armed || grant_ready || batch_done || !core_bank_locked || stop_reason!=5)$fatal(1,"Core fault was treated as safe drain");
        $display("PASS lease: invalid grants/interlock stop fail closed; core fault remains quarantined without resetting or releasing a locked bank.");
        $display("PASS raw capture lease controller regression.");$finish;
    end
    initial begin #100000;$fatal(1,"lease regression timeout");end
endmodule
