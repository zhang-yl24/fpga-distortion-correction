`timescale 1ns/1ps
module tb_frame_ab_dwell;
    reg clk=0,rst_n=0,accept=0,failed=0,commit=0;
    always #4 clk=~clk;
    wire legacy,fast,dwell,production;
    frame_ab_control_reference baseline(clk,rst_n,commit,failed,legacy);
    frame_ab_control #(.HOLD_CYCLES(1)) fast_dut(clk,rst_n,commit,failed,fast);
    frame_ab_control #(.HOLD_CYCLES(9)) dwell_dut(clk,rst_n,commit,failed,dwell);
    frame_ab_control production_parameters(clk,rst_n,commit,failed,production);
    // Probe for the existing actual bank acceptance/registered commit contract.
    // It does not model DDR, RGB pixels, or the complete bank controller.
    reg bank_mode=0;
    always @(posedge clk or negedge rst_n)
        if(!rst_n)begin commit<=0;bank_mode<=0;end
        else begin commit<=accept;if(accept)bank_mode<=dwell;end
    integer age=0,toggles=0,checks=0,commits=0,hold_checks=0;
    reg old_mode,old_commit,old_failed,old_accept,old_bank;
    always @(posedge clk)begin
        old_mode=dwell;old_commit=commit;old_failed=failed;
        old_accept=accept;old_bank=bank_mode;
        if(!rst_n)age=0;else if(!failed)age=age+1;
        #1;
        if(fast!==legacy)$fatal(1,"HOLD_CYCLES1 differs from original selector");
        if(production!==0)$fatal(1,"Production3second parameter changed too early");
        if(rst_n)begin
            checks=checks+1;
            if(old_commit)commits=commits+1;
            if(dwell!==old_mode)begin
                if(!old_commit || old_failed || age<9)$fatal(1,"Mode changed without due committed boundary");
                toggles=toggles+1;age=0;
            end
            if(old_accept && bank_mode!==old_mode)$fatal(1,"Accepted frame did not capture pre-toggle mode");
            if(!old_accept && bank_mode!==old_bank)$fatal(1,"In-flight bank mode changed");
            if(!old_accept)hold_checks=hold_checks+1;
        end
    end
    task cycle;
        input a,f;
        begin accept=a;failed=f;@(posedge clk);#2;@(negedge clk);end
    endtask
    task reset_all;
        begin
            @(negedge clk);rst_n=0;accept=0;failed=0;
            #2;if(dwell!==0 || fast!==0 || bank_mode!==0)$fatal(1,"Reset output contract");
            @(negedge clk);rst_n=1;
        end
    endtask
    integer i;
    initial begin
        reset_all;
        for(i=0;i<8;i=i+1)begin cycle(1,0);if(dwell!==0)$fatal(1,"Dwell shorter than9cycles");end
        cycle(1,0);if(dwell!==1 || bank_mode!==0)$fatal(1,"Due toggle/old-frame mode boundary");
        cycle(1,0);if(bank_mode!==1)$fatal(1,"Next accepted frame missed new mode");
        for(i=0;i<13;i=i+1)cycle(0,0);
        if(dwell!==1)$fatal(1,"Elapsed timer toggled without a commit");
        cycle(1,0);if(dwell!==1 || bank_mode!==1)$fatal(1,"New acceptance must retain old mode");
        cycle(0,0);if(dwell!==0 || bank_mode!==1)$fatal(1,"Registered commit did not defer mode for later frame");
        cycle(1,0);if(bank_mode!==0)$fatal(1,"Later frame did not use new mode");
        for(i=0;i<12;i=i+1)begin cycle(1,1);if(dwell!==0)$fatal(1,"Failure changed mode");end
        reset_all;
        for(i=0;i<8;i=i+1)begin cycle(1,0);if(dwell!==0)$fatal(1,"Reset did not restart full dwell");end
        cycle(1,0);if(dwell!==1)$fatal(1,"Reset restart terminal boundary");
        for(i=0;i<80;i=i+1)cycle((i%5)!=0,(i>=25 && i<30));
        if(checks<100 || toggles<5 || hold_checks<20)$fatal(1,"Coverage witnesses missing");
        $display("FRAME_AB_DWELL_PASS checks=%0d toggles=%0d commits=%0d bank_hold=%0d production_cycles=375000000",checks,toggles,commits,hold_checks);
        $finish;
    end
    initial begin #20000;$fatal(1,"Watchdog");end
endmodule
