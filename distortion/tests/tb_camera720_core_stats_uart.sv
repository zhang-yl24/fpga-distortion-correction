`timescale 1ns/1ps
// Reduced nominal clock/cadence; real uart_tx runs, observed only at its TX pin.
module stats_wire_observer #(parameter FILE_NAME="bytes.hex")(
    input clk,rst_n,tx,output integer bytes_seen=0,aborted_bytes=0
);
    integer fd,bit_index;
    reg [7:0] received;
    reg valid_byte;
    initial begin
        fd=$fopen(FILE_NAME,"w");
        if(!fd)$fatal(1,"cannot open UART wire output");
        forever begin
            @(negedge tx);
            if(rst_n)begin
                valid_byte=1;
                // BIT_CYCLES=10: first data sample is 1.5 bit periods later.
                repeat(15)begin @(posedge clk);#1;if(!rst_n)valid_byte=0;end
                for(bit_index=0;bit_index<8;bit_index=bit_index+1)begin
                    received[bit_index]=tx;
                    repeat(10)begin @(posedge clk);#1;if(!rst_n)valid_byte=0;end
                end
                if(valid_byte)begin
                    if(tx!==1'b1)$fatal(1,"UART stop bit was not high");
                    $fdisplay(fd,"%02x",received);bytes_seen=bytes_seen+1;
                end else aborted_bytes=aborted_bytes+1;
            end
        end
    end
endmodule

module tb_camera720_core_stats_uart;
    reg clk=0,rst_n=0;
    always #5 clk=~clk;
    reg [31:0] accepted=0,processed=0,presented=0;
    reg status_valid=0,failed=0;reg [7:0] fault=0;
    wire tx_main,tx_slow;
    integer epoch=0,elapsed=0,input_steps=0,golden,summary;
    wire integer main_bytes,slow_bytes,main_aborted,slow_aborted;
    localparam [63:0] TICK_SEED=64'h00000000ffffd8f0;

    camera720_core_stats_uart #(.CLOCK_HZ(100000),.BAUD(10000),.SAMPLE_CYCLES(10000),
        .BUILD_ID(64'h123456789abcdef0),.PROFILE_ID(64'hfedcba9876543210)) normal(
        .clk(clk),.rst_n(rst_n),.source_accepted(accepted),.processed(processed),
        .unique_presented(presented),.status_valid(status_valid),.failed(failed),.fault(fault),.tx(tx_main));
    camera720_core_stats_uart #(.CLOCK_HZ(100000),.BAUD(10000),.SAMPLE_CYCLES(1000),
        .BUILD_ID(64'h123456789abcdef0),.PROFILE_ID(64'hfedcba9876543210)) oversubscribed(
        .clk(clk),.rst_n(rst_n),.source_accepted(accepted),.processed(processed),
        .unique_presented(presented),.status_valid(status_valid),.failed(failed),.fault(fault),.tx(tx_slow));
    stats_wire_observer #(.FILE_NAME("main-wire.hex")) observe_main(
        .clk(clk),.rst_n(rst_n),.tx(tx_main),.bytes_seen(main_bytes),.aborted_bytes(main_aborted));
    stats_wire_observer #(.FILE_NAME("slow-wire.hex")) observe_slow(
        .clk(clk),.rst_n(rst_n),.tx(tx_slow),.bytes_seen(slow_bytes),.aborted_bytes(slow_aborted));

    // Inputs keep changing during UART transmission. Independent scheduled
    // observations, not DUT snapshot registers, provide the software oracle.
    always @(negedge clk)begin
        if(!rst_n)begin
            input_steps=0;
            accepted<=32'hfffffe00+epoch*1024;
            processed<=32'hffffff80+epoch*1024;
            presented<=32'hffffff40+epoch*1024;
            status_valid<=0;failed<=0;fault<=8'ha2;
        end else begin
            input_steps=input_steps+1;
            if(input_steps%37==0)accepted<=accepted+1'b1;
            if(input_steps%83==0)processed<=processed+1'b1;
            if(input_steps%127==0)presented<=presented+1'b1;
            status_valid<=input_steps>=15000;
            failed<=input_steps>=28000;
            fault<=input_steps>=28000 ? 8'ha2:8'h00;
        end
    end
    always @(posedge clk)begin
        if(!rst_n)elapsed=0;
        else begin
            elapsed=elapsed+1;
            if(elapsed%10000==0)
                $fdisplay(golden,"main,%0d,%0d,%0d,%08x,%08x,%08x,%0d,%0d,%02x",
                    epoch,elapsed/10000-1,elapsed,accepted,processed,presented,
                    status_valid,status_valid&&failed,status_valid ? fault:8'b0);
            if(elapsed%1000==0)
                $fdisplay(golden,"slow,%0d,%0d,%0d,%08x,%08x,%08x,%0d,%0d,%02x",
                    epoch,elapsed/1000-1,TICK_SEED+elapsed,accepted,processed,presented,
                    status_valid,status_valid&&failed,status_valid ? fault:8'b0);
        end
    end

    initial begin
        golden=$fopen("scheduled-snapshots.csv","w");
        $fdisplay(golden,"stream,epoch,sequence,ticks,accepted,processed,presented,status_valid,failed,fault");
        repeat(5)@(negedge clk);
        #1;rst_n=1;oversubscribed.core_ticks=TICK_SEED;
        repeat(35000)@(negedge clk);
        #1;epoch=1;rst_n=0;
        repeat(20)@(negedge clk);
        #1;rst_n=1;oversubscribed.core_ticks=TICK_SEED;
        repeat(39000)@(negedge clk);
        #2;
        if(main_bytes<320 || slow_bytes<576)$fatal(1,"too few UART bytes");
        if(main_aborted+slow_aborted<1)$fatal(1,"mid-byte reset was not exercised");
        summary=$fopen("summary.json","w");
        $fdisplay(summary,"{\"Passed\":true,\"Epochs\":2,\"MainBytes\":%0d,\"SlowBytes\":%0d,\"AbortedBytes\":%0d,\"TickSeed\":%0d}",
            main_bytes,slow_bytes,main_aborted+slow_aborted,TICK_SEED);
        $fclose(summary);$fclose(golden);
        $display("CAMERA720_CORE_STATS_UART_PASS");$finish;
    end
    initial begin #1000000;$fatal(1,"statistics simulation timeout");end
endmodule
