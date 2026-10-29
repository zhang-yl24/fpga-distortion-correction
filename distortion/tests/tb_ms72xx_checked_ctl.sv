`timescale 1ns/1ps
// This bench runs REAL RX/TX sequencers with a TRANSACTION-LEVEL driver stub.
// It is NOT wire-level I2C evidence. The checked driver's line bench is separate.
module tb_ms72xx_checked_ctl;
    reg clk=0, rst_n=0;
    tri1 scl, sda;
    wire rx_done, done, failed;
    wire [3:0] error_code;
    integer scenario, cycles, before_count, hold_cycle, summary;
    reg seen_rx_done,seen_done;
    ms72xx_checked_ctl dut(.clk(clk),.rst_n(rst_n),.init_over_rx(rx_done),
        .init_over(done),.init_failed(failed),.error_code(error_code),
        .iic_scl(scl),.iic_sda(sda));
    always #50 clk=~clk;

    task assert_failure_held;
    begin
        if(!failed || error_code!==4'h4 || rx_done!==0 || done!==0)
            $fatal(1,"failure was not sticky or successful completion escaped scenario=%0d",scenario);
        if(dut.seq_rst_n!==0 || dut.tx_rst_n!==0 || dut.driver_trig!==0)
            $fatal(1,"sequencer reset/request not gated by failure");
        before_count=dut.driver.total_requests;
        for(hold_cycle=0;hold_cycle<40;hold_cycle=hold_cycle+1)begin
            @(negedge clk);
            if(!failed || error_code!==4'h4 || rx_done!==0 || done!==0 ||
               dut.driver.total_requests!=before_count || dut.driver_trig!==0 ||
               dut.seq_rst_n!==0 || dut.tx_rst_n!==0)
                $fatal(1,"failure autoretried or lost evidence");
        end
    end
    endtask

    // Observe without waiting for a later cfg edge: raw failure and busy fall
    // deliberately coincide in the model, including the final setting write.
    always @(posedge dut.driver.transaction_failed) begin
        #1;
        if(rx_done!==0 || done!==0 || dut.seq_rst_n!==0 || dut.driver_trig!==0)
            $fatal(1,"same-cycle failure escaped completion/reset gates");
    end

    initial begin
        for(scenario=0;scenario<7;scenario=scenario+1)begin
            @(negedge clk);rst_n=0;
            dut.driver.scenario=scenario;
            repeat(8)@(negedge clk);
            if(rx_done!==0 || done!==0 || failed!==0 || error_code!==0)
                $fatal(1,"common reset did not clear all public status");
            rst_n=1;seen_rx_done=0;seen_done=0;cycles=0;
            repeat(2)begin
                @(negedge clk);
                if(dut.cfg_rst_n!==0 || dut.driver_trig!==0)
                    $fatal(1,"configuration reset deasserted asynchronously");
            end
            if(scenario==0 || scenario==6)begin
                while(!done)begin
                    @(negedge clk);cycles=cycles+1;
                    if(failed)$fatal(1,"unexpected nominal failure");
                    if(cycles>3300000)$fatal(1,"nominal wrapper initialization timeout");
                end
                if(!rx_done || dut.driver.rx_initial!=300 || dut.driver.rx_settings!=7 ||
                   dut.driver.tx_writes!=49)
                    $fatal(1,"init completion before all actual commands");
                $display("MS72XX_SCENARIO_PASS scenario=%0d rx_init=%0d rx_settings=%0d tx_writes=%0d",
                    scenario,dut.driver.rx_initial,dut.driver.rx_settings,dut.driver.tx_writes);
            end else begin
                while(!failed)begin
                    @(negedge clk);cycles=cycles+1;
                    if(rx_done)seen_rx_done=1;
                    if(done)seen_done=1;
                    if(scenario==2 && rx_done)$fatal(1,"last RX failure advertised RX completion");
                    if(cycles>3300000)$fatal(1,"injected failure not reached scenario=%0d",scenario);
                    if(done && scenario!=5)$fatal(1,"failed initialization advertised success");
                end
                if(scenario>=3 && !seen_rx_done)$fatal(1,"post-RX failure boundary not exercised");
                if(scenario==5 && !seen_done)$fatal(1,"post-completion failure never reached success");
                assert_failure_held();
                $display("MS72XX_SCENARIO_PASS scenario=%0d failure_code=%h requests=%0d",
                    scenario,error_code,dut.driver.total_requests);
            end
        end
        summary=$fopen("summary.json","w");
        $fdisplay(summary,"{\"Passed\":true,\"Scenarios\":7,\"ActualRXControllerExecuted\":true,\"ActualTXControllerExecuted\":true,\"TransactionDriverStub\":true,\"WireLevelI2CExecuted\":false,\"EarlyRXFailure\":true,\"LastRXSettingFailure\":true,\"FirstTXFailureAfterRXDone\":true,\"LastTXWriteFailure\":true,\"PostCompletionFailure\":true,\"CommonResetRecovery\":true,\"FailureSameCycleGating\":true,\"NoAutoRetry\":true,\"HardwareAccessed\":false}");
        $fclose(summary);
        $display("MS72XX_CHECKED_CTL_SIM_PASS");
        $finish;
    end
endmodule

// Same interface as iic_dri_checked, but deliberately NOT that implementation.
// Replies implement scratch echo, RX readiness progression, and command checks.
// Success byte_over precedes busy falling by >=2 clocks; failure drops busy and
// raises sticky transaction_failed together, with no byte_over.
module iic_dri_checked #(parameter CLK_FRE=10000000,IIC_FREQ=400000,T_WR=1,
    ADDR_BYTE=2,LEN_WIDTH=3,DATA_BYTE=1,TIMEOUT_CYCLES=100000)(
    input wire clk,rstn,pluse,
    input wire [7:0] device_id,
    input wire w_r,
    input wire [LEN_WIDTH:0] byte_len,
    input wire [ADDR_BYTE*8-1:0] addr,
    input wire [7:0] data_in,
    output reg busy=0,byte_over=0,
    output reg [7:0] data_out=0,
    output wire scl, input wire scl_in,sda_in,
    output wire sda_out,sda_out_en,
    output reg transaction_failed=0,
    output reg [3:0] error_code=0
);
    integer scenario=0,total_requests=0,rx_transactions=0,tx_transactions=0;
    integer rx_initial=0,rx_settings=0,rx_status=0,tx_writes=0;
    integer remaining=0,duration=0;
    reg [2:0] trigger_pipe=0;
    reg [23:0] expected_rx[0:310],expected_tx[0:48];
    reg [7:0] response;
    reg fail_this;
    assign scl=1'b1;assign sda_out=1'b0;assign sda_out_en=1'b0;
    initial begin
        $readmemh("rx_expected.hex",expected_rx);
        $readmemh("tx_expected.hex",expected_tx);
    end
    task check_request;
    begin
        response=0;fail_this=0;
        if(byte_len!==1)$fatal(1,"wrapper changed transaction length");
        if(device_id==8'h56)begin
            if(rx_transactions==0)begin
                if(!w_r || addr!==16'h0003 || data_in!==8'h5a)
                    $fatal(1,"RX scratch write differs");
            end else if(rx_transactions==1)begin
                if(w_r || addr!==16'h0003)$fatal(1,"RX scratch read differs");
                response=8'h5a;
            end else if(rx_initial<300)begin
                if(!w_r || {addr,data_in}!==expected_rx[rx_initial])
                    $fatal(1,"RX init command mismatch index=%0d",rx_initial);
                rx_initial=rx_initial+1;
            end else if(w_r)begin
                if(rx_settings>=7 || {addr,data_in}!==expected_rx[304+rx_settings])
                    $fatal(1,"RX settings mismatch index=%0d",rx_settings);
                rx_settings=rx_settings+1;
                if(scenario==2 && rx_settings==7)fail_this=1;
            end else begin
                if(addr!==16'h209c+rx_status%4)$fatal(1,"RX status ordering changed");
                response=(addr==16'h209e && rx_status>=4)?8'h02:8'h00;
                rx_status=rx_status+1;
                if(scenario==5 && tx_writes==49)fail_this=1;
            end
            if(scenario==1 && rx_transactions==0)fail_this=1;
            rx_transactions=rx_transactions+1;
        end else if(device_id==8'hb2)begin
            if(rx_initial!=300 || rx_settings!=7)$fatal(1,"TX acquired bus before RX done");
            if(tx_transactions==0)begin
                if(!w_r || addr!==16'h0003 || data_in!==8'h5a)
                    $fatal(1,"TX scratch write differs");
                if(scenario==3)fail_this=1;
            end else if(tx_transactions==1)begin
                if(w_r || addr!==16'h0003)$fatal(1,"TX scratch read differs");
                response=8'h5a;
            end else begin
                if(tx_writes>=49 || !w_r || {addr,data_in}!==expected_tx[tx_writes])
                    $fatal(1,"TX command mismatch index=%0d actual=%h expected=%h",
                        tx_writes,{addr,data_in},expected_tx[tx_writes]);
                tx_writes=tx_writes+1;
                if(scenario==4 && tx_writes==49)fail_this=1;
            end
            tx_transactions=tx_transactions+1;
        end else $fatal(1,"invalid slave address");
        total_requests=total_requests+1;
    end
    endtask
    always @(posedge clk or negedge rstn)begin
        if(!rstn)begin
            busy<=0;byte_over<=0;data_out<=0;transaction_failed<=0;error_code<=0;
            trigger_pipe<=0;remaining=0;total_requests=0;
            rx_transactions=0;tx_transactions=0;rx_initial=0;rx_settings=0;
            rx_status=0;tx_writes=0;
        end else begin
            trigger_pipe<={trigger_pipe[1:0],pluse};
            byte_over<=0;
            if(!transaction_failed)begin
                if(!busy && trigger_pipe[1] && !trigger_pipe[2])begin
                    check_request();busy<=1;duration=12+(total_requests%5)*7;remaining=duration;
                end else if(busy)begin
                    remaining=remaining-1;
                    if(remaining==3 && !fail_this)begin byte_over<=1;data_out<=response;end
                    if(remaining==0)begin
                        busy<=0;
                        if(fail_this)begin transaction_failed<=1;error_code<=4'h4;end
                    end
                end
            end
        end
    end
endmodule

