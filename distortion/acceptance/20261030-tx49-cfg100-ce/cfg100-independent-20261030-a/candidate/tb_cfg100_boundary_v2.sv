`timescale 1ns/1ps
module tb_cfg100_boundary;
    reg clk=0,clock_run=1,chip_reset_n=0,locked=0;
    always #50 if(clock_run)clk=~clk;
    wire q1,q7,qd;
    cfg100_startup_hold #(.SETTLE_CYCLES(1)) h1(clk,chip_reset_n,locked,q1);
    cfg100_startup_hold #(.SETTLE_CYCLES(7)) h7(clk,chip_reset_n,locked,q7);
    cfg100_startup_hold hd(clk,chip_reset_n,locked,qd);
    wire scl1,scld,rx1,done1,rxd,doned;tri1 sda1,sdad;
    ms72xx_cfg100_ctl w1(.clk(clk),.rst_n(q1),.init_over_rx(rx1),.init_over(done1),.iic_scl(scl1),.iic_sda(sda1));
    ms72xx_cfg100_ctl wd(.clk(clk),.rst_n(qd),.init_over_rx(rxd),.init_over(doned),.iic_scl(scld),.iic_sda(sdad));
    integer cycles=0,first_eligible_sample=0,n1_releases=0,n7_releases=0,default_releases=0;
    integer stopped_resets=0,starts1=0,startsd=0,phase=0;
    time default_arm_time,default_release_time;
    always @(posedge clk)cycles=cycles+1;
    always @(posedge q1)begin
        if(cycles!=first_eligible_sample+3)$fatal(1,"CFG_BOUNDARY N1 early/late edge");
        n1_releases=n1_releases+1;
    end
    always @(posedge q7)begin
        if(cycles!=first_eligible_sample+9)$fatal(1,"CFG_BOUNDARY N7 early/late edge");
        n7_releases=n7_releases+1;
    end
    always @(posedge hd.armed)default_arm_time=$time;
    always @(posedge qd)begin
        if(cycles!=first_eligible_sample+1000002)$fatal(1,"CFG_BOUNDARY default incorrect edge count");
        if($time-default_arm_time!=100000000)$fatal(1,"CFG_BOUNDARY default not100ms");
        default_release_time=$time;default_releases=default_releases+1;
        $display("CFG_DEFAULT_MEASURED periods=1000000 period_ns=100 elapsed_ns=%0d",$time-default_arm_time);
    end
    always @(negedge sda1)if(chip_reset_n && scl1===1)begin
        if(q1!==1)$fatal(1,"CFG_BOUNDARY small IIC START before release");starts1=starts1+1;
    end
    always @(negedge sdad)if(chip_reset_n && scld===1)begin
        if(qd!==1 || $time<=default_release_time)$fatal(1,"CFG_BOUNDARY default IIC START before release");
        startsd=startsd+1;
    end
    task release_chip(input bit lock_value);begin
        @(negedge clk);#17;locked=lock_value;chip_reset_n=1;
        if(lock_value)first_eligible_sample=cycles+1;
    end endtask
    task stopped_reset;begin
        @(negedge clk);clock_run=0;#17;chip_reset_n=0;#2;
        if(q1!==0 || q7!==0 || qd!==0 || w1.rstn!==0 || wd.rstn!==0 ||
           rx1!==0 || done1!==0 || rxd!==0 || doned!==0 || scl1!==1 || scld!==1 || sda1!==1 || sdad!==1)
            $fatal(1,"CFG_BOUNDARY stopped clock did not assert reset control/pins");
        #200;chip_reset_n=1;#200;
        if(q1!==0 || q7!==0 || qd!==0)$fatal(1,"CFG_BOUNDARY released without a cfg edge");
        chip_reset_n=0;stopped_resets=stopped_resets+1;#100;clock_run=1;
        repeat(8)@(negedge clk);
        if(w1.iic_dri.trans_en!==0 || w1.iic_dri.busy!==0 || w1.iic_dri.start_en!==0 || w1.iic_dri.scl_out!==1)
            $fatal(1,"CFG_BOUNDARY stale IIC transfer after common reset");
    end endtask
    initial begin
        repeat(8)@(negedge clk);
        phase=1;release_chip(0);repeat(15)@(negedge clk);
        if(q1 || q7 || qd)$fatal(1,"CFG_BOUNDARY released without observed lock");
        #17;locked=1;first_eligible_sample=cycles+1;
        wait(starts1>0);wait(scl1===0 && w1.iic_dri.trans_en===1);#2;
        if(!q1 || !q7 || qd)$fatal(1,"CFG_BOUNDARY unexpected first partial state");
        stopped_reset();
        phase=2;release_chip(1);wait(q1);#2;
        if(q7 || qd)$fatal(1,"CFG_BOUNDARY longer counts bypassed");
        stopped_reset();
        phase=3;release_chip(1);wait(q7);#2;
        // Both small gates have released. Only still-waiting default restarts.
        @(negedge clk);#17;locked=0;repeat(12)@(negedge clk);
        if(!q1 || !q7 || qd)$fatal(1,"CFG_BOUNDARY startup/runtime lock semantics changed");
        #17;locked=1;first_eligible_sample=cycles+1;
        wait(qd);wait(startsd>0);#2;
        @(negedge clk);#17;locked=0;repeat(12)@(negedge clk);
        if(!q1 || !q7 || !qd)$fatal(1,"CFG_BOUNDARY runtime lock reset feedback");
        stopped_reset();
        if(n1_releases!=3 || n7_releases!=2 || default_releases!=1 || stopped_resets!=3 || startsd<1)
            $fatal(1,"CFG_BOUNDARY coverage incomplete");
        $display("CFG_BOUNDARY_PASS N1=%0d N7=%0d default=%0d stopped_resets=%0d first_default_START=%0d",n1_releases,n7_releases,default_releases,stopped_resets,startsd);
        $finish;
    end
    initial begin #120000000;$fatal(1,"CFG_BOUNDARY watchdog");end
endmodule
