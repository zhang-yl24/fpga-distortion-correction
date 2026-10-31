`timescale 1ns/1ps
// Existing TX-only controller and real, default-parameter reg16_i2c.
// No internal forces, counter changes, transaction stubs, or RX controller.
module tb_hdmi_tx_init;
    reg clk=0;
    always #18.518518 clk=~clk; // 27 MHz contract, including all original delays.
    reg rst_n=0;
    tri1 scl, sda;
    reg slave_sda=0;
    assign sda=slave_sda ? 1'b0 : 1'bz;
    wire ready;
    wire [3:0] error;
    hdmi_tx_init dut(.clk(clk),.rst_n(rst_n),.hd_scl(scl),.hd_sda(sda),
                     .ready(ready),.error(error));
    reg [23:0] expected [0:48];
    longint cycles=0, start_cycle, previous_stop, reset_cycle, error_cycle;
    integer scenario=-1, transactions=0, starts=0, stops=0, table_writes=0;
    integer trace, summary, epoch_starts;
    reg table_finished=0;
    always @(posedge clk) cycles<=cycles+1;
    always @(negedge sda) if(rst_n && scl===1'b1) starts=starts+1;
    always @(posedge sda) if(rst_n && scl===1'b1) stops=stops+1;
    always @(negedge clk) if(rst_n && ready &&
            (scenario!=0 || !table_finished || error!=0))
        $fatal(1,"Ready before complete successful TX-only sequence");

    task automatic wait_start;
        begin
            @(negedge sda);
            if(scl!==1'b1) $fatal(1,"Missing START");
            start_cycle=cycles;
        end
    endtask
    task automatic receive(input [7:0] expected_byte, input bit ack);
        reg [7:0] value;
        begin
            value=0;
            for(integer bitnum=0; bitnum<8; bitnum=bitnum+1) begin
                @(posedge scl); value={value[6:0],sda};
            end
            if(value!==expected_byte)
                $fatal(1,"Wire byte expected %h got %h scenario=%0d",expected_byte,value,scenario);
            @(negedge scl); slave_sda=ack;
            @(posedge scl); @(negedge scl); slave_sda=0;
        end
    endtask
    task automatic send(input [7:0] value);
        begin
            for(integer bitnum=7; bitnum>=0; bitnum=bitnum-1) begin
                slave_sda=!value[bitnum]; @(posedge scl); @(negedge scl);
            end
            slave_sda=0; @(posedge scl);
            if(sda!==1'b1) $fatal(1,"Final read byte must be master NACK");
            @(negedge scl);
        end
    endtask
    task automatic wait_stop;
        begin
            do @(posedge sda); while(scl!==1'b1);
            previous_stop=cycles;
        end
    endtask
    task automatic write_register(input [15:0] addr, input [7:0] value,
                                  input integer minimum_gap);
        longint gap;
        begin
            wait_start(); gap=start_cycle-previous_stop;
            if(gap<minimum_gap) $fatal(1,"Inter-command delay too short %0d < %0d",gap,minimum_gap);
            receive(8'hb2,1); // Only 7-bit 0x59, never MS7200 0x56.
            receive(addr[7:0],1); receive(addr[15:8],1); receive(value,1);
            wait_stop(); transactions=transactions+1;
            $fdisplay(trace,"%0d,%0d,b2,0,%04h,%02h,00,0,%0d",scenario,transactions,addr,value,gap);
        end
    endtask
    task automatic read_signature(input [7:0] response);
        begin
            wait_start();
            receive(8'hb2,1); receive(8'h03,1); receive(8'h00,1);
            wait_start(); receive(8'hb3,1); send(response); wait_stop();
            transactions=transactions+1;
            $fdisplay(trace,"%0d,%0d,b2,1,0003,00,%02h,0,0",scenario,transactions,response);
        end
    endtask
    task automatic reset_epoch(input integer number);
        begin
            @(negedge clk); rst_n=0; slave_sda=0; scenario=number;
            table_finished=0; table_writes=0; transactions=0;
            repeat(10) @(negedge clk);
            if(ready!==0 || error!==0 || scl!==1 || sda!==1)
                $fatal(1,"Reset failed to release outputs");
            epoch_starts=starts; previous_stop=cycles; reset_cycle=cycles;
            rst_n=1;
        end
    endtask

    initial begin
        $readmemh("tx_expected.hex",expected);
        trace=$fopen("wire-transactions.csv","w");
        if(!trace) $fatal(1,"Cannot open trace");
        $fdisplay(trace,"scenario,request,device,read,addr,data,response,nack,gap_cycles");
        reset_epoch(0);
        write_register(16'h0003,8'h5a,270000);
        if(start_cycle-reset_cycle<270000) $fatal(1,"Initial 10ms wait too short");
        read_signature(8'h5a);
        for(integer index=0; index<49; index=index+1) begin
            write_register(expected[index][23:8],expected[index][7:0],
                           index==0 ? 0 : index==19 ? 8100000 : 27000);
            table_writes=table_writes+1;
        end
        table_finished=1;
        wait(ready===1); @(negedge clk);
        if(error!==0 || transactions!=51 || table_writes!=49 || starts-epoch_starts!=52)
            $fatal(1,"Successful transaction count/ready differs");
        repeat(100) @(negedge clk);
        if(starts-epoch_starts!=52 || scl!==1 || sda!==1)
            $fatal(1,"Unexpected traffic after ready");
        $display("HDMI_TX_ONLY_SCENARIO_PASS scenario=0 writes=49 transactions=51");

        reset_epoch(1);
        wait_start(); receive(8'hb2,0); wait_stop(); transactions=transactions+1;
        $fdisplay(trace,"1,1,b2,0,0000,00,00,1,0");
        wait(error!=0); @(negedge clk); error_cycle=cycles;
        if(error!==4'h1 || ready) $fatal(1,"Device NACK must report error1 without ready");
        // Observe the entire original retry hold. No internal counters are touched.
        fork
            begin
                wait_start();
                if(start_cycle-error_cycle<27270000)
                    $fatal(1,"Retry START before 1s error hold + 10ms startup delay");
            end
            begin
                wait(error==0); @(negedge clk);
                if(cycles-error_cycle<26999999 || ready)
                    $fatal(1,"Error cleared before full 27M-cycle retry interval");
            end
        join
        @(negedge clk); // Resolve the independent START event monitor first.
        if(starts-epoch_starts!=2 || ready)
            $fatal(1,"Retry START count differs");
        $display("HDMI_TX_ONLY_SCENARIO_PASS scenario=1 nack_error=1 retry_start_delay_cycles=%0d",start_cycle-error_cycle);
        // The retry START is covered; retry completion is deliberately not covered.

        reset_epoch(2);
        write_register(16'h0003,8'h5a,270000); read_signature(8'ha5);
        wait(error!=0); @(negedge clk);
        if(error!==4'he || ready || transactions!=2 || starts-epoch_starts!=3)
            $fatal(1,"Scratch mismatch must report errorE without ready/table writes");
        repeat(1000) @(negedge clk);
        if(error!==4'he || ready || starts-epoch_starts!=3)
            $fatal(1,"Mismatch fault hold differs");
        $display("HDMI_TX_ONLY_SCENARIO_PASS scenario=2 signature_error=14 transactions=2");
        $fclose(trace);
        summary=$fopen("summary.json","w");
        $fdisplay(summary,"{\"Passed\":true,\"Scenarios\":3,\"VendorTableWrites\":49,\"ActualControllerExecuted\":true,\"ActualDriverExecuted\":true,\"WireLevelI2CExecuted\":true,\"ClockHz\":27000000,\"InternalCountersModified\":false,\"RXControllerExecuted\":false,\"NACKWithoutReady\":true,\"SignatureMismatchWithoutReady\":true,\"FullRetryMinimumDelayVerified\":true,\"RetryCompletionCovered\":false,\"HardwareAccessed\":false}");
        $fclose(summary);
        $display("HDMI_TX_ONLY_SIM_PASS"); $finish;
    end
    initial begin #2000000000; $fatal(1,"Bounded TX-only test timeout"); end
endmodule
