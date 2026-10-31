`timescale 1ns/1ps
// Real unchanged MS7200 sequencer; transaction stub only, not wire-level I2C.
// The stimulus changes only returned receiver status, never DUT internals.
module tb_ms7200_ready_level;
    reg clk=0,rstn=0;
    wire init_over,iic_trig,w_r;
    wire [7:0] device_id,data_in;
    wire [15:0] addr;
    reg busy=0,byte_over=0;
    reg [7:0] data_out=0;
    reg [2:0] trigger_pipe=0;
    reg [7:0] ready_value=8'h02,response=0;
    integer remaining=0,requests=0,initial_writes=0,status_reads=0;
    integer ready_reads=0,setting_writes=0,cycles=0,trace,summary;
    integer blocked_ready_reads=0,blocked_requests=0;
    integer low_start_reads=0,recovery_cycles=0,normal_cycles=0;
    reg auto_ready_after_first=0;
    ms7200_ctl dut(.clk(clk),.rstn(rstn),.init_over(init_over),.device_id(device_id),
        .iic_trig(iic_trig),.w_r(w_r),.addr(addr),.data_in(data_in),
        .busy(busy),.data_out(data_out),.byte_over(byte_over));
    always #50 clk=~clk;

    always @(posedge clk)begin
        if(!rstn)begin
            busy<=0;byte_over<=0;data_out<=0;trigger_pipe<=0;
            remaining=0;requests=0;initial_writes=0;status_reads=0;
            ready_reads=0;setting_writes=0;
        end else begin
            trigger_pipe<={trigger_pipe[1:0],iic_trig};byte_over<=0;
            if(!busy && trigger_pipe[1] && !trigger_pipe[2])begin
                response=0;
                if(device_id!==8'h56)$fatal(1,"unexpected device");
                if(requests==0)begin
                    if(!w_r || addr!==16'h0003 || data_in!==8'h5a)$fatal(1,"scratch write differs");
                end else if(requests==1)begin
                    if(w_r || addr!==16'h0003)$fatal(1,"scratch read differs");
                    response=8'h5a;
                end else if(initial_writes<300)begin
                    if(!w_r)$fatal(1,"initial command changed to read");
                    initial_writes=initial_writes+1;
                end else if(w_r)begin
                    if(dut.state!==dut.SETING)$fatal(1,"unexpected post-init write");
                    setting_writes=setting_writes+1;
                end else begin
                    if(addr!==16'h209c+status_reads%4)$fatal(1,"status order differs");
                    status_reads=status_reads+1;
                    if(addr==16'h209e)begin
                        response=ready_value;
                        ready_reads=ready_reads+1;
                        if(auto_ready_after_first && ready_reads>=1)ready_value=8'h02;
                    end
                end
                requests=requests+1;
                $fdisplay(trace,"%0t,%0d,%0d,%04h,%02h,%02h,%02h,%0d,%0d",
                    $time,requests,w_r,addr,data_in,response,dut.state,dut.freq_ensure,init_over);
                busy<=1;remaining=17+(requests%5);
            end else if(busy)begin
                remaining=remaining-1;
                if(remaining==3)begin data_out<=response;byte_over<=1;end
                if(remaining==0)busy<=0;
            end
        end
    end

    task wait_for_done;
        output integer count;
    begin
        count=0;
        while(init_over!==1'b1)begin
            @(negedge clk);count=count+1;
            if(count>30000)$fatal(1,"init did not complete after explicit ready edge");
        end
        if(initial_writes!=300 || setting_writes!=7)$fatal(1,"done before full initialization");
    end
    endtask

    initial begin
        trace=$fopen("transactions.csv","w");
        $fdisplay(trace,"time_ns,request,write,address,write_value,response,state,freq_ensure,init_over");
        repeat(8)@(negedge clk);rstn=1;
        cycles=0;
        // Case A: readiness is already 02 at every first/next status read.
        while(ready_reads<64)begin
            @(negedge clk);cycles=cycles+1;
            if(init_over!==0 || setting_writes!=0)$fatal(1,"stable-ready unexpectedly initialized");
            if(cycles>30000)$fatal(1,"did not reach 64 ready reads");
        end
        repeat(60)@(negedge clk);
        if(init_over!==0 || setting_writes!=0 || dut.freq_ensure!==0 ||
           dut.freq_rec_2d[17:16]!==2'b10 || dut.freq_rec_1d[17:16]!==2'b10)
            $fatal(1,"stable-ready counterexample not established");
        blocked_ready_reads=ready_reads;blocked_requests=requests;
        $display("MS7200_STABLE_READY_BLOCKED ready_reads=%0d requests=%0d initial_writes=%0d setting_writes=%0d init_over=%0d prior_ready=%02b current_ready=%02b",
            ready_reads,requests,initial_writes,setting_writes,init_over,dut.freq_rec_2d[17:16],dut.freq_rec_1d[17:16]);

        // Case B: no reset; external source disconnect/reconnect is modeled
        // by two complete status reads with 00, then persistent 02.
        @(negedge clk);ready_value=8'h00;low_start_reads=ready_reads;
        while(ready_reads<low_start_reads+2)@(negedge clk);
        repeat(60)@(negedge clk);
        if(init_over!==0 || setting_writes!=0)$fatal(1,"zero readiness initialized receiver");
        ready_value=8'h02;
        wait_for_done(recovery_cycles);
        $display("MS7200_READY_EDGE_RECOVERY_PASS ready_reads=%0d setting_writes=%0d init_over=%0d cycles_after_edge=%0d",
            ready_reads,setting_writes,init_over,recovery_cycles);

        // Case C: standard reference stimulus supplies 00 once, then 02.
        @(negedge clk);rstn=0;ready_value=0;auto_ready_after_first=1;
        repeat(8)@(negedge clk);rstn=1;
        wait_for_done(normal_cycles);
        $display("MS7200_INITIAL_ZERO_THEN_READY_PASS ready_reads=%0d setting_writes=%0d init_over=%0d",
            ready_reads,setting_writes,init_over);
        summary=$fopen("summary.json","w");
        $fdisplay(summary,"{\"CounterexampleReproduced\":true,\"StableReadyValue\":2,\"StableReadyReadsBeforeRecovery\":%0d,\"StableReadyRequestsBeforeRecovery\":%0d,\"StableReadyInitOver\":false,\"StableReadySettingWrites\":0,\"InitialWritesCompleted\":300,\"SameEpochZeroThenTwoRecovered\":true,\"NormalZeroThenTwoCompleted\":true,\"SettingsWritesWhenCompleted\":7,\"TransactionDriverStub\":true,\"WireLevelI2CExecuted\":false,\"HardwareAccessed\":false}",blocked_ready_reads,blocked_requests);
        $fclose(summary);$fclose(trace);
        $display("MS7200_READY_LEVEL_COUNTEREXAMPLE_PASS");
        $finish;
    end
endmodule
