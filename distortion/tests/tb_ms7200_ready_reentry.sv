`timescale 1ns/1ps
// A/B real sequencers with a bounded successful-transaction response model.
// No hierarchical assignments/forces; this is not a wire-level I2C slave.
module ready_reentry_case #(parameter REARM=0)(output reg done=0);
    reg clk=0,rstn=0;
    always #50 clk=~clk;
    wire init_over,iic_trig,w_r;
    wire [7:0] device_id,data_in;
    wire [15:0] addr;
    reg busy=0,byte_over=0;
    reg [7:0] data_out=0,ready_value=0,response=0;
    reg [2:0] trigger_pipe=0;
    wire sample_seen;
    wire [1:0] previous_ready;
    wire [3:0] status_valid;
    wire [6:0] state;
    generate if(REARM)begin:new_candidate
        ms7200_1080p30_rearm_ctl dut(.clk(clk),.rstn(rstn),.init_over(init_over),
            .device_id(device_id),.iic_trig(iic_trig),.w_r(w_r),.addr(addr),
            .data_in(data_in),.busy(busy),.data_out(data_out),.byte_over(byte_over));
        assign sample_seen=dut.status_sample_seen;
        assign previous_ready=dut.previous_ready;
        assign status_valid=dut.status_read_valid;
        assign state=dut.state;
    end else begin:old_candidate
        ms7200_1080p30_ready_ctl dut(.clk(clk),.rstn(rstn),.init_over(init_over),
            .device_id(device_id),.iic_trig(iic_trig),.w_r(w_r),.addr(addr),
            .data_in(data_in),.busy(busy),.data_out(data_out),.byte_over(byte_over));
        assign sample_seen=dut.status_sample_seen;
        assign previous_ready=dut.previous_ready;
        assign status_valid=dut.status_read_valid;
        assign state=dut.state;
    end endgenerate
    reg [23:0] expected[0:310];
    reg suppress_terminal=0,deliver_byte=1;
    integer remaining=0,requests=0,initial_writes=0,status_reads=0;
    integer terminal_reads=0,setting_writes=0,scenario=0,trace,summary;
    integer count=0,start_polls=0,expected_settings=0,passed_cases=0;
    initial $readmemh("rx_expected.hex",expected);

    always @(posedge clk)begin
        if(!rstn)begin
            busy<=0;byte_over<=0;data_out<=0;trigger_pipe<=0;
            remaining=0;requests=0;initial_writes=0;status_reads=0;
            terminal_reads=0;setting_writes=0;
        end else begin
            trigger_pipe<={trigger_pipe[1:0],iic_trig};byte_over<=0;
            if(!busy && trigger_pipe[1] && !trigger_pipe[2])begin
                response=0;deliver_byte=1;
                if(device_id!==8'h56)$fatal(1,"wrong RX device");
                if(requests==0)begin
                    if(!w_r || addr!==16'h0003 || data_in!==8'h5a)$fatal(1,"scratch write differs");
                end else if(requests==1)begin
                    if(w_r || addr!==16'h0003)$fatal(1,"scratch read differs");
                    response=8'h5a;
                end else if(initial_writes<300)begin
                    if(!w_r || {addr,data_in}!==expected[initial_writes])
                        $fatal(1,"initial table changed rearm=%0d index=%0d",REARM,initial_writes);
                    initial_writes=initial_writes+1;
                end else if(w_r)begin
                    if(state!==7'b0100000 || {addr,data_in}!==expected[304+setting_writes%7])
                        $fatal(1,"setting order changed rearm=%0d index=%0d",REARM,setting_writes);
                    setting_writes=setting_writes+1;
                end else begin
                    if(addr!==16'h209c+status_reads%4)$fatal(1,"status order differs");
                    status_reads=status_reads+1;
                    if(addr==16'h209e)response=ready_value;
                    if(addr==16'h209f)begin
                        terminal_reads=terminal_reads+1;
                        if(suppress_terminal)begin deliver_byte=0;suppress_terminal=0;end
                    end
                end
                requests=requests+1;
                $fdisplay(trace,"%0d,%0d,%0t,%0d,%0d,%04h,%02h,%02h,%0d,%02h,%0d",
                    REARM,scenario,$time,requests,w_r,addr,data_in,response,deliver_byte,state,init_over);
                busy<=1;remaining=17+(requests%5);
            end else if(busy)begin
                remaining=remaining-1;
                if(remaining==3 && deliver_byte)begin data_out<=response;byte_over<=1;end
                if(remaining==0)busy<=0;
            end
        end
    end

    task restart(input [7:0] ready,input bit suppress);
        begin
            @(negedge clk);rstn=0;ready_value=ready;suppress_terminal=suppress;
            repeat(8)@(negedge clk);
            if(init_over!==0 || sample_seen!==0 || previous_ready!==0 || status_valid!==0)
                $fatal(1,"reset history not cleared");
            rstn=1;
        end
    endtask
    task wait_more_polls(input integer extra);
        integer target;
        begin
            target=terminal_reads+extra;count=0;
            while(terminal_reads<target || busy)begin
                @(negedge clk);count=count+1;
                if(count>40000)$fatal(1,"poll timeout rearm=%0d case=%0d",REARM,scenario);
            end
            repeat(4)@(negedge clk);
        end
    endtask
    task await_settings(input integer wanted);
        begin
            count=0;
            while(setting_writes<wanted || init_over!==1)begin
                @(negedge clk);count=count+1;
                if(count>40000)$fatal(1,"setting timeout rearm=%0d case=%0d",REARM,scenario);
            end
            wait_more_polls(3);
            if(setting_writes!=wanted || initial_writes!=300 || !init_over)
                $fatal(1,"unexpected repeat or missing commands");
        end
    endtask
    task mark(input string label);
        begin
            passed_cases=passed_cases+1;
            $display("MS7200_REENTRY_CASE rearm=%0d scenario=%0d label=%s settings=%0d PASS",
                REARM,scenario,label,setting_writes);
        end
    endtask
    task transition_after_init(input [7:0] not_ready,input integer case_id,input string label);
        begin
            scenario=case_id;restart(8'h02,0);await_settings(7);
            @(negedge clk);ready_value=not_ready;wait_more_polls(3);
            if(previous_ready!==not_ready[1:0] || setting_writes!=7)$fatal(1,"not-ready history missing");
            @(negedge clk);ready_value=8'h02;
            expected_settings=(REARM || not_ready==0)?14:7;
            if(expected_settings==14)await_settings(14);else wait_more_polls(8);
            if(setting_writes!=expected_settings)$fatal(1,"re-entry admission differs from A/B contract");
            wait_more_polls(33);
            if(setting_writes!=expected_settings)$fatal(1,"stable ready replayed settings");
            mark(label);
        end
    endtask

    initial begin
        trace=$fopen(REARM ? "rearm-transactions.csv":"old-transactions.csv","w");
        if(trace==0)$fatal(1,"trace file unavailable");
        $fdisplay(trace,"rearm,scenario,time_ns,request,write,address,value,response,completion,state,init_over");
        scenario=0;restart(8'h02,0);await_settings(7);mark("first_ready02");
        scenario=1;wait_more_polls(33);
        if(setting_writes!=7)$fatal(1,"stable02 retriggered");
        mark("stable02_no_repeat");
        transition_after_init(8'h03,2,"complete03_to02_after_init");
        transition_after_init(8'h01,3,"complete01_to02_after_init");
        transition_after_init(8'h00,4,"complete00_to02_after_init");

        scenario=5;restart(8'h03,0);wait_more_polls(4);
        if(init_over || setting_writes || previous_ready!==2'b11)$fatal(1,"03 wrongly admitted");
        @(negedge clk);ready_value=8'h02;
        if(REARM)await_settings(7);else wait_more_polls(8);
        if(setting_writes!=(REARM?7:0))$fatal(1,"cold03_to02 differs");
        mark("cold03_to02");

        scenario=6;restart(8'h01,0);wait_more_polls(4);
        if(init_over || setting_writes || previous_ready!==2'b01)$fatal(1,"01 wrongly admitted");
        @(negedge clk);ready_value=8'h02;
        if(REARM)await_settings(7);else wait_more_polls(8);
        if(setting_writes!=(REARM?7:0))$fatal(1,"cold01_to02 differs");
        mark("cold01_to02");

        scenario=7;restart(8'h02,0);await_settings(7);mark("common_reset_rearms_first02");

        scenario=8;restart(8'h02,1);
        count=0;
        while(terminal_reads<1 || busy)begin
            @(negedge clk);count=count+1;
            if(count>40000)$fatal(1,"incomplete poll timeout");
        end
        repeat(3)@(negedge clk);
        if(init_over || setting_writes || sample_seen)$fatal(1,"incomplete poll admitted");
        await_settings(7);mark("incomplete_terminal_poll_rejected");

        scenario=9;restart(8'h03,0);wait_more_polls(8);
        @(negedge clk);ready_value=8'h01;wait_more_polls(8);
        @(negedge clk);ready_value=8'h00;wait_more_polls(8);
        if(init_over || setting_writes)$fatal(1,"non02 state admitted settings");
        mark("nonready03_01_00_blocked");
        if(passed_cases!=10)$fatal(1,"case coverage incomplete");
        summary=$fopen(REARM ? "rearm-summary.json":"old-summary.json","w");
        $fdisplay(summary,"{\"Passed\":true,\"Rearm\":%0d,\"Cases\":10,\"InitialCommandsPerEpoch\":300,\"SettingsPerAdmission\":7,\"Stable02DoesNotRepeat\":true,\"IncompletePollRejected\":true,\"TransactionDriverStub\":true,\"WireLevelI2CExecuted\":false,\"HardwareAccessed\":false}",REARM);
        $fclose(summary);$fclose(trace);done=1;
    end
endmodule

module tb_ms7200_ready_reentry;
    wire old_done,new_done;
    ready_reentry_case #(.REARM(0)) old_case(.done(old_done));
    ready_reentry_case #(.REARM(1)) new_case(.done(new_done));
    initial begin
        wait(old_done && new_done);
        $display("MS7200_READY_REENTRY_AB_SIM_PASS");$finish;
    end
    initial begin #50000000;$fatal(1,"bounded A/B simulation timeout");end
endmodule
