`timescale 1ns/1ps
module tb_thermal_idle_telemetry;
    reg clk=0;always #18.5 clk=~clk;
    reg rst_n=0,sample_valid=1,failed=0,over_temp=0;
    reg [7:0] fault=0;reg [15:0] raw_word=16'h98df;reg [11:0] code12=12'h98d;
    reg [31:0] sample_age=32'h1234,samples=3,conversions=7;reg [4:0] alarm=0;
    wire byte_valid,byte_ready,byte_done;wire [7:0] byte_data;
    wire record_started,record_done;wire [31:0] record_sequence;
    wire tx,busy,uart_done;reg hold_last_done=1,injected_done=0;
    integer received=0,starts=0,finishes=0,outfile;reg [7:0] decoded;
    thermal_idle_telemetry #(.REPORT_CYCLES(16)) dut(.*);
    uart_tx #(.CLOCK_HZ(27000000),.BAUD(921600)) serial(
        .clk(clk),.rst_n(rst_n),.start(byte_valid && byte_ready),.data(byte_data),.tx(tx),.busy(busy),.done(uart_done));
    assign byte_ready=!busy;
    assign byte_done=hold_last_done && received==125 ? injected_done:uart_done;
    // Decode the physical 8N1 wire independently at the implemented 29-clock
    // bit period. No byte-level loopback substitutes for the UART serializer.
    always begin
        @(negedge tx);
        if(rst_n)begin
            #536.5;if(tx!==0)$fatal(1,"Bad UART start bit");
            for(integer bit_index=0;bit_index<8;bit_index=bit_index+1)begin #1073;decoded[bit_index]=tx;end
            #1073;if(tx!==1)$fatal(1,"Bad UART stop bit");
            $fwrite(outfile,"%c",decoded);received=received+1;
            if(received>250)$fatal(1,"Extra snapshot byte");
        end
    end
    always @(posedge clk)begin
        if(record_started)starts=starts+1;
        if(record_done)finishes=finishes+1;
    end
    initial begin
        outfile=$fopen("thermal-idle-synthetic-lines.txt","wb");
        repeat(8)@(negedge clk);rst_n=1;
        wait(record_started);@(negedge clk);
        // Change every source field while the first line is still in flight.
        // The first record must retain the entire original tuple, the second
        // must expose the complete invalid/fault/over-temperature tuple.
        sample_valid=0;failed=1;fault=8'h04;raw_word=16'h000f;code12=0;
        sample_age=32'h87654321;samples=8;conversions=12;over_temp=1;alarm=5'h15;
        wait(received==125);
        repeat(40)@(negedge clk);
        if(record_sequence!=1 || finishes!=0 || starts!=1)$fatal(1,"Tail byte_done was bypassed or next snapshot overlapped");
        injected_done=1;wait(record_done);@(negedge clk);injected_done=0;hold_last_done=0;
        wait(received==250);wait(record_done);repeat(2)@(negedge clk);
        if(starts!=2 || finishes!=2 || record_sequence!=2)$fatal(1,"Snapshot count mismatch");
        $fclose(outfile);
        $display("PASS thermal idle UART: frozen full-field snapshots, failed/invalid/over-temp visibility, actual 921600-parameter 8N1 wire, final byte_done and no overlapping records; verify CRC/fields independently.");
        $finish;
    end
    initial begin #10000000;$fatal(1,"Thermal UART regression timeout received=%d",received);end
endmodule
