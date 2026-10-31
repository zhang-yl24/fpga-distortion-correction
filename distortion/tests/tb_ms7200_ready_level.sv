`timescale 1ns/1ps
// Real isolated ready-level controller; transaction response model only.
// No hierarchical assignments or forces modify the controller state.
module tb_ms7200_ready_level;
    reg clk=0,rstn=0;
    wire init_over,iic_trig,w_r;
    wire [7:0] device_id,data_in;
    wire [15:0] addr;
    reg busy=0,byte_over=0;
    reg [7:0] data_out=0,ready_value=0,response=0;
    reg [2:0] trigger_pipe=0;
    reg auto_ready_after_first=0,suppress_one_terminal_byte=0,deliver_byte=1;
    integer remaining=0,requests=0,initial_writes=0,status_reads=0;
    integer ready_reads=0,setting_writes=0,scenario=0,trace,summary;
    integer cycles=0,previous_polls=0,summary_cold_cycles=0,completion_ready_reads=0;
    reg [23:0] expected[0:310];
    ms7200_1080p30_ready_ctl dut(.clk(clk),.rstn(rstn),.init_over(init_over),.device_id(device_id),
        .iic_trig(iic_trig),.w_r(w_r),.addr(addr),.data_in(data_in),
        .busy(busy),.data_out(data_out),.byte_over(byte_over));
    always #50 clk=~clk;
    initial $readmemh("rx_expected.hex",expected);

    always @(posedge clk)begin
        if(!rstn)begin
            busy<=0;byte_over<=0;data_out<=0;trigger_pipe<=0;
            remaining=0;requests=0;initial_writes=0;status_reads=0;
            ready_reads=0;setting_writes=0;
        end else begin
            trigger_pipe<={trigger_pipe[1:0],iic_trig};byte_over<=0;
            if(!busy && trigger_pipe[1] && !trigger_pipe[2])begin
                response=0;deliver_byte=1;
                if(device_id!==8'h56)$fatal(1,"unexpected device");
                if(requests==0)begin
                    if(!w_r || addr!==16'h0003 || data_in!==8'h5a)$fatal(1,"scratch write differs");
                end else if(requests==1)begin
                    if(w_r || addr!==16'h0003)$fatal(1,"scratch read differs");
                    response=8'h5a;
                end else if(initial_writes<300)begin
                    if(!w_r || {addr,data_in}!==expected[initial_writes])
                        $fatal(1,"initial register command differs index=%0d",initial_writes);
                    initial_writes=initial_writes+1;
                end else if(w_r)begin
                    if(dut.state!==dut.SETING || {addr,data_in}!==expected[304+setting_writes%7])
                        $fatal(1,"setting command differs index=%0d",setting_writes);
                    setting_writes=setting_writes+1;
                end else begin
                    if(addr!==16'h209c+status_reads%4)$fatal(1,"status order differs");
                    status_reads=status_reads+1;
                    if(addr==16'h209e)begin
                        response=ready_value;ready_reads=ready_reads+1;
                        if(auto_ready_after_first && ready_reads>=1)ready_value=8'h02;
                    end
                    if(addr==16'h209f && suppress_one_terminal_byte)begin
                        deliver_byte=0;suppress_one_terminal_byte=0;
                    end
                end
                requests=requests+1;
                $fdisplay(trace,"%0d,%0t,%0d,%0d,%04h,%02h,%02h,%0d,%02h,%0d,%0d",
                    scenario,$time,requests,w_r,addr,data_in,response,deliver_byte,
                    dut.state,dut.freq_ensure,init_over);
                busy<=1;remaining=17+(requests%5);
            end else if(busy)begin
                remaining=remaining-1;
                if(remaining==3 && deliver_byte)begin data_out<=response;byte_over<=1;end
                if(remaining==0)busy<=0;
            end
        end
    end

    task restart;
        input [7:0] ready;
        input automatic_edge;
        input suppress_terminal;
    begin
        @(negedge clk);rstn=0;ready_value=ready;
        auto_ready_after_first=automatic_edge;suppress_one_terminal_byte=suppress_terminal;
        repeat(8)@(negedge clk);
        if(init_over!==0 || dut.status_sample_seen!==0 || dut.previous_ready!==0 ||
           dut.status_read_valid!==0 || dut.busy_1d!==0)
            $fatal(1,"reset did not clear readiness history");
        rstn=1;
    end
    endtask

    task wait_settings;
        input integer wanted;
    begin
        cycles=0;
        while(setting_writes<wanted || init_over!==1)begin
            @(negedge clk);cycles=cycles+1;
            if(cycles>30000)$fatal(1,"settings completion timeout scenario=%0d",scenario);
        end
        completion_ready_reads=ready_reads;
        repeat(60)@(negedge clk);
        if(initial_writes!=300 || setting_writes!=wanted || init_over!==1)
            $fatal(1,"incomplete or repeated initialization scenario=%0d",scenario);
    end
    endtask

    task wait_polls;
        input integer wanted;
    begin
        cycles=0;
        while(ready_reads<wanted)begin
            @(negedge clk);cycles=cycles+1;
            if(cycles>30000)$fatal(1,"polling timeout scenario=%0d",scenario);
        end
        repeat(60)@(negedge clk);
    end
    endtask

    initial begin
        trace=$fopen("transactions.csv","w");
        $fdisplay(trace,"scenario,time_ns,request,write,address,write_value,response,byte_over_delivered,state,freq_ensure,init_over");
        // 0: Cold start with readiness already asserted on the first poll.
        scenario=0;restart(8'h02,0,0);wait_settings(7);summary_cold_cycles=cycles;
        if(completion_ready_reads!=1)$fatal(1,"first complete ready poll was not accepted");
        $display("MS7200_READY_CANDIDATE_SCENARIO_PASS scenario=0 cold_already_ready=1 settings=%0d",setting_writes);

        // 1: More than 32 additional steady-ready polls must not write again.
        scenario=1;previous_polls=ready_reads;wait_polls(previous_polls+33);
        if(setting_writes!=7 || init_over!==1)$fatal(1,"steady readiness retriggered settings");
        $display("MS7200_READY_CANDIDATE_SCENARIO_PASS scenario=1 steady_ready_no_reconfigure=1 settings=%0d",setting_writes);

        // 2: Retain original later 00-to-02 relock behavior without reset.
        scenario=2;@(negedge clk);ready_value=0;previous_polls=ready_reads;
        wait_polls(previous_polls+2);
        if(dut.previous_ready!==0 || setting_writes!=7)$fatal(1,"not-ready history was not held");
        ready_value=8'h02;wait_settings(14);
        $display("MS7200_READY_CANDIDATE_SCENARIO_PASS scenario=2 later_relock=1 settings=%0d",setting_writes);

        // 3: A common reset clears the previous ready history and admits 02.
        scenario=3;restart(8'h02,0,0);wait_settings(7);
        if(completion_ready_reads!=1)$fatal(1,"reset did not restore first-poll admission");
        $display("MS7200_READY_CANDIDATE_SCENARIO_PASS scenario=3 reset_ready_history=1 settings=%0d",setting_writes);

        // 4: Preserve the conventional initial 00 then stable 02 case.
        scenario=4;restart(8'h00,1,0);wait_settings(7);
        if(completion_ready_reads!=2)$fatal(1,"normal readiness edge changed");
        $display("MS7200_READY_CANDIDATE_SCENARIO_PASS scenario=4 initial_zero_then_ready=1 settings=%0d",setting_writes);

        // 5: Constant not-ready never starts the seven setting writes.
        scenario=5;restart(8'h00,0,0);wait_polls(33);
        if(init_over!==0 || setting_writes!=0 || dut.status_sample_seen!==1 || dut.previous_ready!==0)
            $fatal(1,"constant not-ready initialized receiver");
        $display("MS7200_READY_CANDIDATE_SCENARIO_PASS scenario=5 constant_not_ready=1 settings=%0d",setting_writes);

        // 6: Missing byte_over on a terminal read cannot establish history.
        scenario=6;restart(8'h02,0,1);
        cycles=0;
        while(status_reads<4 || busy!==0)begin
            @(negedge clk);cycles=cycles+1;
            if(cycles>30000)$fatal(1,"incomplete poll scenario timeout");
        end
        repeat(3)@(negedge clk);
        if(init_over!==0 || setting_writes!=0 || dut.status_sample_seen!==0)
            $fatal(1,"incomplete first poll established readiness");
        wait_settings(7);
        if(completion_ready_reads!=2)$fatal(1,"first subsequent complete ready poll did not recover");
        $display("MS7200_READY_CANDIDATE_SCENARIO_PASS scenario=6 incomplete_poll_rejected=1 settings=%0d",setting_writes);

        summary=$fopen("summary.json","w");
        $fdisplay(summary,"{\"Passed\":true,\"Scenarios\":7,\"ColdAlreadyReadyCompleted\":true,\"SteadyReadyDoesNotReconfigure\":true,\"LaterZeroToTwoRelockCompleted\":true,\"ResetClearsReadyHistory\":true,\"NormalZeroToTwoCompleted\":true,\"ConstantNotReadyBlocked\":true,\"IncompletePollRejected\":true,\"InitialWritesPerEpoch\":300,\"SettingsPerAdmission\":7,\"TransactionDriverStub\":true,\"WireLevelI2CExecuted\":false,\"HardwareAccessed\":false}");
        $fclose(summary);$fclose(trace);
        $display("MS7200_READY_CANDIDATE_SIM_PASS");$finish;
    end
endmodule
