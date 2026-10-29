`timescale 1ns/1ps
// Real checked driver + real HDMI30 RX and isolated checked TX sequencers.
// Slave replies are synthetic: this proves digital protocols, not PHY lock/AC.
module tb_ms72xx_checked_e2e;
    reg clk=0,rst_n=0;always #50 clk=~clk;
    tri1 scl,sda;reg slave_sda=0;assign sda=slave_sda?1'b0:1'bz;
    wire rx_done,done,failed;wire [3:0] error_code;
    ms72xx_checked_ctl dut(.clk(clk),.rst_n(rst_n),.init_over_rx(rx_done),
        .init_over(done),.init_failed(failed),.error_code(error_code),.iic_scl(scl),.iic_sda(sda));
    reg [23:0] expected_rx[0:310],expected_tx[0:48];
    integer scenario,cycles,rx_transactions,tx_transactions,rx_initial,rx_settings,rx_status,tx_writes;
    integer total_requests,old_requests,hold_cycle,fd,summary;
    reg seen_rx_done,seen_done;
    reg [7:0] dev,lo,hi,payload,response;
    reg [15:0] register_addr;reg read_request,inject_fault;
    reg [3:0] expected_error;
    task wait_start;begin do @(negedge sda);while(scl!==1);end endtask
    task receive(output reg [7:0] value,input bit ack);
        begin
            value=0;
            for(integer bitno=0;bitno<8;bitno=bitno+1)begin
                @(posedge scl);value={value[6:0],sda};
            end
            @(negedge scl);slave_sda=ack;
            @(posedge scl);@(negedge scl);slave_sda=0;
        end
    endtask
    task send(input [7:0] value);
        begin
            for(integer bitno=7;bitno>=0;bitno=bitno-1)begin
                slave_sda=!value[bitno];@(posedge scl);@(negedge scl);
            end
            slave_sda=0;@(posedge scl);
            if(sda!==1)$fatal(1,"master did not NACK final read byte");
            @(negedge scl);
        end
    endtask
    task wait_stop;begin do @(posedge sda);while(scl!==1);end endtask

    task slave_transaction;
        reg [7:0] read_id;
        begin
            wait_start();receive(dev,1);receive(lo,1);receive(hi,1);
            register_addr={hi,lo};response=0;inject_fault=0;read_request=0;
            if(dev==8'h56)begin
                read_request=(rx_transactions==1) || (rx_transactions>=302 &&
                    ((rx_status<8) || rx_settings==7));
                if(read_request)begin
                    if(rx_transactions==1)begin
                        if(register_addr!==16'h0003)$fatal(1,"RX scratch read wire address");
                        response=8'h5a;
                    end else begin
                        if(register_addr!==16'h209c+rx_status%4)
                            $fatal(1,"RX status wire address got%h expected%h",register_addr,16'h209c+rx_status%4);
                        response=(register_addr==16'h209e && rx_status>=4)?8'h02:8'h00;
                        rx_status=rx_status+1;
                        if(scenario==5 && tx_writes==49)inject_fault=1;
                    end
                end else begin
                    if(scenario==1 && rx_transactions==0)inject_fault=1;
                    if(scenario==2 && rx_initial==300 && rx_settings==6)inject_fault=1;
                end
            end else if(dev==8'hb2)begin
                if(rx_initial!=300 || rx_settings!=7)$fatal(1,"TX started before RX completion");
                read_request=(tx_transactions==1);
                if(read_request)begin
                    if(register_addr!==16'h0003)$fatal(1,"TX scratch read wire address");
                    response=8'h5a;
                end
                if(scenario==3 && tx_transactions==0)inject_fault=1;
                if(scenario==4 && tx_writes==48)inject_fault=1;
            end else $fatal(1,"wire slave address differs %h",dev);
            if(read_request)begin
                wait_start();receive(read_id,!inject_fault);
                if(read_id!==(dev|8'h01))$fatal(1,"repeatedSTART slave address differs");
                if(!inject_fault)send(response);
                payload=0;
            end else begin
                receive(payload,!inject_fault);
                if(dev==8'h56)begin
                    if(rx_transactions==0)begin
                        if({register_addr,payload}!==24'h00035a)$fatal(1,"RX scratch write wire value");
                    end else if(rx_initial<300)begin
                        if({register_addr,payload}!==expected_rx[rx_initial])
                            $fatal(1,"RX command wire mismatch index%0d",rx_initial);
                        rx_initial=rx_initial+1;
                    end else begin
                        if(rx_settings>=7 || {register_addr,payload}!==expected_rx[304+rx_settings])
                            $fatal(1,"RX setting wire mismatch index%0d",rx_settings);
                        rx_settings=rx_settings+1;
                    end
                end else begin
                    if(tx_transactions==0)begin
                        if({register_addr,payload}!==24'h00035a)$fatal(1,"TX scratch write wire value");
                    end else begin
                        if(tx_writes>=49 || {register_addr,payload}!==expected_tx[tx_writes])
                            $fatal(1,"TX command wire mismatch index%0d actual%h expected%h",
                                tx_writes,{register_addr,payload},expected_tx[tx_writes]);
                        tx_writes=tx_writes+1;
                    end
                end
            end
            wait_stop();
            total_requests=total_requests+1;
            $fdisplay(fd,"%0d,%0d,%02h,%0d,%04h,%02h,%02h,%0d",
                scenario,total_requests,dev,read_request,register_addr,payload,response,inject_fault);
            if(dev==8'h56)rx_transactions=rx_transactions+1;else tx_transactions=tx_transactions+1;
        end
    endtask

    always @(posedge dut.driver.transaction_failed)begin
        #1;
        if(rx_done!==0 || done!==0 || dut.seq_rst_n!==0 || dut.driver_trig!==0)
            $fatal(1,"same-cycle driver fault escaped wrapper gates");
    end
    initial begin
        $readmemh("rx_expected.hex",expected_rx);$readmemh("tx_expected.hex",expected_tx);
        fd=$fopen("wire-transactions.csv","w");
        $fdisplay(fd,"scenario,request,device,read,addr,data,response,nack");
        for(scenario=0;scenario<7;scenario=scenario+1)begin
            @(negedge clk);rst_n=0;slave_sda=0;
            repeat(8)@(negedge clk);
            if(done || rx_done || failed || error_code)$fatal(1,"global reset did not clear flags");
            rx_transactions=0;tx_transactions=0;rx_initial=0;rx_settings=0;rx_status=0;tx_writes=0;
            total_requests=0;cycles=0;seen_rx_done=0;seen_done=0;
            expected_error=(scenario==5)?4'h5:4'h4;
            fork : epoch
                begin forever slave_transaction();end
                begin
                    @(negedge clk);rst_n=1;
                    if(scenario==0 || scenario==6)begin
                        while(!done || rx_status<12 || dut.driver_busy)begin
                            @(negedge clk);cycles=cycles+1;
                            if(failed)$fatal(1,"nominal end-to-end initialization failed");
                            if(cycles>4200000)$fatal(1,"end-to-end initialization or RXpoll timeout");
                        end
                        if(!rx_done || rx_initial!=300 || rx_settings!=7 || tx_writes!=49)
                            $fatal(1,"full command set incomplete");
                    end else begin
                        while(!failed)begin
                            @(negedge clk);cycles=cycles+1;
                            if(rx_done)seen_rx_done=1;if(done)seen_done=1;
                            if(scenario==2 && rx_done)$fatal(1,"last RX NACK advertised RX completion");
                            if(done && scenario!=5)$fatal(1,"failing initialization exposed success");
                            if(cycles>4200000)$fatal(1,"wire NACK scenario timeout %0d",scenario);
                        end
                        if(scenario>=3 && !seen_rx_done)$fatal(1,"postRX failure not reached");
                        if(scenario==5 && !seen_done)$fatal(1,"postinit RXpoll failure not reached");
                        old_requests=total_requests;
                        for(hold_cycle=0;hold_cycle<40;hold_cycle=hold_cycle+1)begin
                            @(negedge clk);
                            if(!failed || error_code!==expected_error || done || rx_done ||
                               total_requests!=old_requests || dut.driver_trig ||
                               dut.seq_rst_n!==0 || dut.tx_rst_n!==0)
                                $fatal(1,"wire fault not sticky or retried");
                        end
                    end
                    $display("MS72XX_E2E_SCENARIO_PASS scenario=%0d requests=%0d rx_init=%0d rx_settings=%0d tx_writes=%0d status=%0d code=%h",
                        scenario,total_requests,rx_initial,rx_settings,tx_writes,rx_status,error_code);
                end
            join_any
            disable epoch;
        end
        $fclose(fd);summary=$fopen("summary.json","w");
        $fdisplay(summary,"{\"Passed\":true,\"Scenarios\":7,\"ActualRXControllerExecuted\":true,\"ActualTXControllerExecuted\":true,\"TransactionDriverStub\":false,\"WireLevelI2CExecuted\":true,\"EarlyRXFailure\":true,\"LastRXSettingFailure\":true,\"FirstTXFailureAfterRXDone\":true,\"LastTXWriteFailure\":true,\"PostCompletionFailure\":true,\"CommonResetRecovery\":true,\"FailureSameCycleGating\":true,\"NoAutoRetry\":true,\"BackgroundRXPollResumed\":true,\"HardwareAccessed\":false}");
        $fclose(summary);$display("MS72XX_CHECKED_E2E_SIM_PASS");$finish;
    end
endmodule

