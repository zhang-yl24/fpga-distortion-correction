`timescale 1ns/1ps
// Real checked driver + real HDMI30 RX and isolated checked TX sequencers.
// Slave replies are synthetic: this proves digital protocols, not PHY lock/AC.
// Wire CSV and reference vectors retain the checked bench schema.
// The telemetry oracle uses actual wire bytes and completed STOPs, never the
// driver's byte_over, live sequencer addresses, or observed active_* taps.
module tb_ms72xx_observed_e2e;
    reg clk=0,rst_n=0;always #50 clk=~clk;
    tri1 scl,sda;reg slave_sda=0;assign sda=slave_sda?1'b0:1'bz;
    wire rx_done,done,failed;wire [3:0] error_code;
    wire [31:0] completed_transactions;
    wire [15:0] last_address;
    wire [7:0] last_value;
    wire [1:0] last_meta;
    ms72xx_ready_observed_ctl dut(.clk(clk),.rst_n(rst_n),.init_over_rx(rx_done),
        .init_over(done),.init_failed(failed),.error_code(error_code),.iic_scl(scl),.iic_sda(sda),
        .completed_transactions(completed_transactions),.last_address(last_address),
        .last_value(last_value),.last_meta(last_meta));
    reg [23:0] expected_rx[0:310],expected_tx[0:48];
    integer scenario,cycles,rx_transactions,tx_transactions,rx_initial,rx_settings,rx_status,tx_writes;
    integer total_requests,old_requests,hold_cycle,fd,summary;
    reg seen_rx_done,seen_done;
    reg [7:0] dev,lo,hi,payload,response;
    reg [15:0] register_addr;reg read_request,inject_fault;
    reg [3:0] expected_error;
    integer telemetry_fd,wire_successes=0,wire_nacks=0,observed_updates=0;
    integer pending_age=0,pending_request=0,all_updates=0,all_nacks=0;
    reg pending_success=0;
    reg [15:0] expected_address=0,previous_address=0;
    reg [7:0] expected_value=0,previous_value=0,wire_read_value=0;
    reg [1:0] expected_meta=0,previous_meta=0;
    reg [31:0] previous_completed=0;

    // One outstanding physical transaction. Queue only after wire STOP.
    // Sample after NBA so the DUT output flops can update on this edge.
    always @(posedge clk) begin
        #2;
        if(!rst_n) begin
            if({completed_transactions,last_address,last_value,last_meta} !== 58'b0)
                $fatal(1,"telemetry did not clear on common reset");
            previous_completed=0;previous_address=0;previous_value=0;previous_meta=0;
            pending_age=0;
        end else begin
            if($isunknown({completed_transactions,last_address,last_value,last_meta}))
                $fatal(1,"unknown telemetry output");
            if(completed_transactions!==previous_completed) begin
                if(!pending_success || completed_transactions!==previous_completed+32'd1 ||
                   completed_transactions!==wire_successes)
                    $fatal(1,"telemetry count before wire STOP, duplicate, skipped, or NACK counted: scenario=%0d got=%0d previous=%0d wire=%0d pending=%0d",
                        scenario,completed_transactions,previous_completed,wire_successes,pending_success);
                if({last_address,last_value,last_meta} !==
                   {expected_address,expected_value,expected_meta})
                    $fatal(1,"wire/telemetry metadata mismatch scenario=%0d request=%0d expected=%h/%h/%h actual=%h/%h/%h",
                        scenario,pending_request,expected_address,expected_value,expected_meta,
                        last_address,last_value,last_meta);
                observed_updates=observed_updates+1;all_updates=all_updates+1;
                $fdisplay(telemetry_fd,"%0d,%0d,%0d,%01h,%04h,%02h",
                    scenario,pending_request,completed_transactions,last_meta,last_address,last_value);
                pending_success=0;pending_age=0;
            end else if({last_address,last_value,last_meta} !==
                        {previous_address,previous_value,previous_meta})
                $fatal(1,"metadata changed without a successful transaction count");
            if(pending_success) begin
                pending_age=pending_age+1;
                if(pending_age>64)$fatal(1,"successful wire STOP not published to telemetry");
            end
            previous_completed=completed_transactions;
            previous_address=last_address;previous_value=last_value;previous_meta=last_meta;
        end
    end

    task verify_telemetry_epoch;
        integer expected_requests;
        begin
            case(scenario)
                0,6:expected_requests=372;
                1:expected_requests=1;
                2:expected_requests=317;
                3:expected_requests=318;
                4:expected_requests=368;
                5:expected_requests=369;
                default:expected_requests=-1;
            endcase
            if(pending_success || total_requests!=expected_requests ||
               wire_nacks!=((scenario==0 || scenario==6)?0:1) ||
               wire_successes+wire_nacks!=total_requests ||
               completed_transactions!==wire_successes || observed_updates!=wire_successes)
                $fatal(1,"telemetry epoch coverage/count differs scenario=%0d requests=%0d wire_success=%0d nacks=%0d observed=%0d published=%0d pending=%0d",
                    scenario,total_requests,wire_successes,wire_nacks,observed_updates,
                    completed_transactions,pending_success);
            $display("MS72XX_OBSERVED_TELEMETRY_PASS scenario=%0d successful=%0d nacks=%0d observed=%0d",
                scenario,wire_successes,wire_nacks,observed_updates);
        end
    endtask
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
            wire_read_value=0;
            for(integer bitno=7;bitno>=0;bitno=bitno-1)begin
                slave_sda=!value[bitno];@(posedge scl);
                if(sda!==value[bitno])$fatal(1,"slave read data differs on the actual wire");
                wire_read_value={wire_read_value[6:0],sda};@(negedge scl);
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
            if(pending_success)$fatal(1,"previous wire completion not observed before next STOP");
            total_requests=total_requests+1;
            if(inject_fault) begin
                wire_nacks=wire_nacks+1;all_nacks=all_nacks+1;
            end else begin
                wire_successes=wire_successes+1;
                expected_address=register_addr;
                expected_value=read_request ? wire_read_value : payload;
                expected_meta={(dev==8'hb2),read_request};
                pending_request=total_requests;pending_age=0;pending_success=1;
            end
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
        telemetry_fd=$fopen("telemetry-transactions.csv","w");
        if(fd==0 || telemetry_fd==0)$fatal(1,"cannot open wire/telemetry evidence");
        $fdisplay(fd,"scenario,request,device,read,addr,data,response,nack");
        $fdisplay(telemetry_fd,"scenario,request,completed,meta,addr,value");
        for(scenario=0;scenario<7;scenario=scenario+1)begin
            @(negedge clk);rst_n=0;slave_sda=0;
            repeat(8)@(negedge clk);
            if(done || rx_done || failed || error_code)$fatal(1,"global reset did not clear flags");
            rx_transactions=0;tx_transactions=0;rx_initial=0;rx_settings=0;rx_status=0;tx_writes=0;
            total_requests=0;cycles=0;seen_rx_done=0;seen_done=0;
            wire_successes=0;wire_nacks=0;observed_updates=0;pending_success=0;
            expected_address=0;expected_value=0;expected_meta=0;pending_request=0;pending_age=0;
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
                    verify_telemetry_epoch();
                    $display("MS72XX_E2E_SCENARIO_PASS scenario=%0d requests=%0d rx_init=%0d rx_settings=%0d tx_writes=%0d status=%0d code=%h",
                        scenario,total_requests,rx_initial,rx_settings,tx_writes,rx_status,error_code);
                end
            join_any
            disable epoch;
        end
        if(all_updates!=2112 || all_nacks!=5)
            $fatal(1,"seven-epoch telemetry coverage incomplete updates=%0d nacks=%0d",all_updates,all_nacks);
        $fclose(fd);$fclose(telemetry_fd);summary=$fopen("summary.json","w");
        $fdisplay(summary,"{\"Passed\":true,\"Scenarios\":7,\"ActualRXControllerExecuted\":true,\"ActualTXControllerExecuted\":true,\"TransactionDriverStub\":false,\"WireLevelI2CExecuted\":true,\"EarlyRXFailure\":true,\"LastRXSettingFailure\":true,\"FirstTXFailureAfterRXDone\":true,\"LastTXWriteFailure\":true,\"PostCompletionFailure\":true,\"CommonResetRecovery\":true,\"FailureSameCycleGating\":true,\"NoAutoRetry\":true,\"BackgroundRXPollResumed\":true,\"TelemetryComparedToWire\":true,\"SuccessfulTelemetryUpdates\":2112,\"NACKTelemetrySuppressed\":5,\"HardwareAccessed\":false}");
        $fclose(summary);$display("MS72XX_OBSERVED_E2E_SIM_PASS");$finish;
    end
endmodule

