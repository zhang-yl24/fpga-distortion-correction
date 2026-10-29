`timescale 1ns/1ps
module tb_iic_dri_checked;
    reg clk=0; always #50 clk=~clk; // Actual board configuration clock: 10MHz.
    reg rstn=0, pluse=0, w_r=1;
    reg [7:0] device_id=8'hb2, data_in=8'ha5;
    reg [15:0] addr=16'h1234;
    reg [3:0] byte_len=1;
    wire busy, byte_over, scl_release, sda_out, sda_out_en, transaction_failed;
    wire [7:0] data_out;
    wire [3:0] error_code;
    wire [8:0] parameter_done;
    iic_invalid_probe #(.ADDR_BYTES(1)) invalid_addr(parameter_done[0]);
    iic_invalid_probe #(.DATA_BYTES(2)) invalid_data(parameter_done[1]);
    iic_invalid_probe #(.FREQUENCY(0)) invalid_zero_frequency(parameter_done[2]);
    iic_invalid_probe #(.FREQUENCY(-1)) invalid_negative_frequency(parameter_done[3]);
    iic_invalid_probe #(.FREQUENCY(400001)) invalid_frequency_limit(parameter_done[4]);
    iic_invalid_probe #(.CLOCK_RATE(100_000_001)) invalid_clock_limit(parameter_done[5]);
    iic_invalid_probe #(.DEADLINE(0)) invalid_timeout(parameter_done[6]);
    iic_invalid_probe #(.WRITE_DELAY(-1)) invalid_write_delay(parameter_done[7]);
    iic_timing_parameter_probe timing_arithmetic(parameter_done[8]);
    tri1 scl,sda;
    reg slave_scl=0, slave_sda=0;
    assign scl=(!scl_release || slave_scl) ? 1'b0 : 1'bz;
    assign sda=slave_sda ? 1'b0 : 1'bz;
    assign sda=sda_out_en ? sda_out : 1'bz;
    iic_dri_checked #(.CLK_FRE(10_000_000),.IIC_FREQ(400_000),.T_WR(1),
        .ADDR_BYTE(2),.LEN_WIDTH(3),.DATA_BYTE(1),.TIMEOUT_CYCLES(8000)) dut(
        .clk(clk),.rstn(rstn),.pluse(pluse),.device_id(device_id),.w_r(w_r),
        .byte_len(byte_len),.addr(addr),.data_in(data_in),.busy(busy),
        .byte_over(byte_over),.data_out(data_out),.scl(scl_release),
        .scl_in(scl),.sda_in(sda),.sda_out(sda_out),.sda_out_en(sda_out_en),
        .transaction_failed(transaction_failed),.error_code(error_code));

    integer cycles=0, starts=0, stops=0, overs=0, accepted_over_cycle=-1;
    integer fd, count=0, base_cycles, base_starts, base_stops, base_overs;
    integer min_low=2147483647, min_high=2147483647;
    integer clock_low_edges=0, clock_high_edges=0;
    time last_rise=0, last_fall=0;
    reg measure_timing=0;
    always @(posedge clk) begin
        cycles<=cycles+1;
        #1;
        if(rstn && byte_over) begin
            if(!busy || transaction_failed || scl!==1 || sda!==1)
                $fatal(1,"Completion before successful STOP/released bus");
            overs=overs+1; accepted_over_cycle=cycles;
        end
        if(rstn && sda_out!==0) $fatal(1,"SDA must never drive high");
        if(rstn && transaction_failed && (byte_over || busy || !scl_release || sda_out_en))
            $fatal(1,"Fault must release outputs and suppress completion");
    end
    always @(negedge sda) if(rstn && scl===1) starts=starts+1;
    always @(posedge sda) if(rstn && scl===1) stops=stops+1;
    always @(posedge scl) begin
        if(measure_timing && last_fall!=0) begin
            if($time-last_fall<1300) $fatal(1,"Fast-mode SCL low below1.3us: %0t",$time-last_fall);
            if($time-last_fall<min_low) min_low=$time-last_fall;
            clock_low_edges=clock_low_edges+1;
        end
        last_rise=$time;
    end
    always @(negedge scl) begin
        if(measure_timing && last_rise!=0) begin
            if($time-last_rise<600) $fatal(1,"Fast-mode SCL high below0.6us: %0t",$time-last_rise);
            if($time-last_rise<min_high) min_high=$time-last_rise;
            clock_high_edges=clock_high_edges+1;
        end
        last_fall=$time;
    end
    task automatic reset_bus;
        begin
            measure_timing=0;
            @(negedge clk); rstn=0; pluse=0; slave_sda=0; slave_scl=0;
            byte_len=1; w_r=1; device_id=8'hb2; addr=16'h1234; data_in=8'ha5;
            repeat(6) @(negedge clk);
            rstn=1; repeat(8) @(negedge clk);
            if(transaction_failed || error_code || busy || byte_over || scl!==1 || sda!==1)
                $fatal(1,"Reset did not restore clean idle");
        end
    endtask
    task automatic mark_case;
        begin
            base_cycles=cycles; base_starts=starts; base_stops=stops; base_overs=overs;
        end
    endtask
    task automatic launch(input bit read_request);
        begin
            @(negedge clk); w_r=!read_request; pluse=1;
            @(negedge clk); pluse=0;
        end
    endtask
    task automatic wait_start;
        begin
            @(negedge sda);
            if(scl!==1) $fatal(1,"Expected START");
        end
    endtask
    task automatic receive(input [7:0] expected, input bit ack);
        reg [7:0] value;
        begin
            value=0;
            for(integer bitno=0;bitno<8;bitno=bitno+1) begin
                @(posedge scl); value={value[6:0],sda};
            end
            if(value!==expected) $fatal(1,"Wire byte expected %02h got %02h",expected,value);
            @(negedge scl); slave_sda=ack;
            @(posedge scl); @(negedge scl); slave_sda=0;
        end
    endtask
    task automatic send(input [7:0] value);
        begin
            for(integer bitno=7;bitno>=0;bitno=bitno-1) begin
                slave_sda=!value[bitno]; @(posedge scl); @(negedge scl);
            end
            slave_sda=0; @(posedge scl);
            if(sda!==1) $fatal(1,"Final read byte must receive master NACK");
            @(negedge scl);
        end
    endtask
    task automatic wait_stop;
        begin do @(posedge sda); while(scl!==1); end
    endtask
    task automatic write_slave;
        begin
            wait_start(); receive(device_id & 8'hfe,1); receive(addr[7:0],1);
            receive(addr[15:8],1); receive(data_in,1); wait_stop();
        end
    endtask
    task automatic read_slave(input [7:0] value,input bit stretch_clock);
        begin
            wait_start(); receive(device_id & 8'hfe,1);
            if(stretch_clock) begin slave_scl=1; repeat(35) @(negedge clk); slave_scl=0; end
            receive(addr[7:0],1); receive(addr[15:8],1);
            wait_start(); receive(device_id | 8'h01,1); send(value); wait_stop();
        end
    endtask
    task automatic successful_done(input bit read_request,input [7:0] expected);
        begin
            launch(read_request); @(posedge busy); @(negedge busy); #2;
            if(transaction_failed || error_code || overs!=base_overs+1)
                $fatal(1,"Expected one successful completion");
            if(cycles-accepted_over_cycle<2) $fatal(1,"busy fell too soon after byte_over");
            if(read_request && data_out!==expected) $fatal(1,"Returned byte expected%h got%h",expected,data_out);
        end
    endtask
    task automatic failed_done(input bit read_request,input [3:0] expected);
        begin
            launch(read_request); @(posedge transaction_failed); #2;
            if(error_code!==expected || busy || overs!=base_overs)
                $fatal(1,"Failure expected%h actual%h busy%0d completion%0d",expected,error_code,busy,overs-base_overs);
        end
    endtask
    task automatic sticky_check(input [3:0] expected);
        integer old_starts, old_overs;
        begin
            old_starts=starts; old_overs=overs;
            slave_sda=0; slave_scl=0; repeat(8) @(negedge clk);
            launch(0); repeat(60) @(negedge clk);
            if(!transaction_failed || error_code!==expected || busy || starts!=old_starts || overs!=old_overs)
                $fatal(1,"Fault must stay latched; new triggers must not retry");
        end
    endtask
    task automatic record(input [8*40-1:0] name,input [3:0] expected);
        begin
            count=count+1;
            $fdisplay(fd,"%0d,%0s,%0d,%0d,%02h,%0d,%0d,%0d,%0d",count,name,expected,error_code,data_out,
                overs-base_overs,starts-base_starts,stops-base_stops,cycles-base_cycles);
            $display("PASS %0s code=%0h completions=%0d",name,error_code,overs-base_overs);
        end
    endtask

    initial begin
        fd=$fopen("iic-checked-cases.csv","w");
        if(fd==0) $fatal(1,"Cannot create case log");
        $fdisplay(fd,"id,name,expected_error,observed_error,read_data,byte_over_count,start_count,stop_count,elapsed_cycles");
        reset_bus(); mark_case(); measure_timing=1;
        fork write_slave(); successful_done(0,0); join
        measure_timing=0; record("write_success",0);

        reset_bus(); mark_case(); device_id=8'h56; addr=16'h209e; measure_timing=1;
        fork read_slave(8'ha6,0); successful_done(1,8'ha6); join
        measure_timing=0; record("read_success",0);

        for(integer stage=1;stage<=5;stage=stage+1) begin
            reset_bus(); mark_case();
            fork
                begin
                    wait_start(); receive(8'hb2,stage!=1);
                    if(stage>1) receive(8'h34,stage!=2);
                    if(stage>2) receive(8'h12,stage!=3);
                    if(stage==4) receive(8'ha5,0);
                    if(stage==5) begin wait_start(); receive(8'hb3,0); end
                    wait_stop();
                end
                failed_done(stage==5,stage[3:0]);
            join
            case(stage)
                1: record("nack_device_write",1);
                2: record("nack_register_low",2);
                3: record("nack_register_high",3);
                4: record("nack_write_data",4);
                5: record("nack_device_read",5);
            endcase
            sticky_check(stage[3:0]);
        end

        reset_bus(); mark_case();
        failed_done(0,1); record("missing_slave",1); sticky_check(1);

        reset_bus(); slave_sda=1; repeat(8) @(negedge clk); mark_case();
        failed_done(0,15); record("sda_stuck_before_start",15); sticky_check(15);

        reset_bus(); slave_scl=1; repeat(8) @(negedge clk); mark_case();
        failed_done(0,15); record("scl_stuck_before_start",15); sticky_check(15);

        reset_bus(); mark_case();
        fork
            begin
                wait_start(); receive(8'hb2,1); receive(8'h34,1); receive(8'h12,1);
                receive(8'ha5,1); slave_sda=1;
            end
            failed_done(0,15);
        join
        record("sda_stuck_at_stop",15); sticky_check(15);

        reset_bus(); mark_case();
        fork read_slave(8'h59,1); successful_done(1,8'h59); join
        record("clock_stretch_read",0);

        reset_bus(); mark_case(); byte_len=2;
        failed_done(0,14); record("unsupported_byte_length",14); sticky_check(14);

        reset_bus(); mark_case();
        fork
            begin wait_start(); receive(8'hb2,1); end
            begin launch(0); @(posedge busy); end
        join
        @(negedge clk); rstn=0; #2;
        if(busy || byte_over || transaction_failed || !scl_release || sda_out_en)
            $fatal(1,"Reset must release active transaction immediately");
        record("reset_during_transaction",0);
        repeat(8) @(negedge clk); rstn=1; repeat(8) @(negedge clk); mark_case();
        fork read_slave(8'h3c,0); successful_done(1,8'h3c); join
        record("read_after_reset_recovery",0);

        reset_bus(); mark_case();
        fork
            write_slave();
            successful_done(0,0);
            begin @(posedge busy); repeat(20) @(negedge clk); pluse=1; @(negedge clk); pluse=0; end
        join
        repeat(40) @(negedge clk);
        if(starts-base_starts!=1 || overs-base_overs!=1) $fatal(1,"Busy request must be ignored");
        record("trigger_while_busy",0);

        reset_bus(); mark_case();
        fork
            begin wait_start(); receive(8'hb2,1); slave_sda=1; end
            failed_done(0,15);
        join
        record("sda_conflict_during_transmit",15); sticky_check(15);
        if(parameter_done!==9'h1ff) $fatal(1,"Parameter guard probes incomplete");
        $fclose(fd);
        fd=$fopen("summary.json","w");
        if(fd==0) $fatal(1,"Cannot create summary");
        $fdisplay(fd,"{\"Passed\":true,\"Cases\":%0d,\"ParameterRejections\":8,\"WideTimingArithmeticChecked\":true,\"ClockHz\":10000000,\"ConfiguredMaximumI2CHz\":400000,\"MinimumSCLLowNs\":%0d,\"MinimumSCLHighNs\":%0d,\"MeasuredLowPhases\":%0d,\"MeasuredHighPhases\":%0d,\"ActualDriverExecuted\":true,\"OpenDrainSlaveModel\":true,\"HardwareAccessed\":false}",count,min_low,min_high,clock_low_edges,clock_high_edges);
        $fclose(fd);
        $display("IIC_DRI_CHECKED_SIM_PASS cases=%0d min_low_ns=%0d min_high_ns=%0d",count,min_low,min_high);
        $finish;
    end
    initial begin #20_000_000; $fatal(1,"Bounded test timeout"); end
endmodule

// Invalid configurations fail before touching either physical wire.
module iic_invalid_probe #(
    parameter ADDR_BYTES=2, DATA_BYTES=1, FREQUENCY=400_000,
    parameter CLOCK_RATE=10_000_000, DEADLINE=8000, WRITE_DELAY=1
)(output reg done=0);
    reg clk=0; always #50 clk=~clk;
    reg rstn=0, trigger=0;
    wire failed,busy,over,scl,oe,data_bit;
    wire [3:0] code;
    wire [7:0] read_data;
    iic_dri_checked #(.CLK_FRE(CLOCK_RATE),.IIC_FREQ(FREQUENCY),.ADDR_BYTE(ADDR_BYTES),
        .DATA_BYTE(DATA_BYTES),.TIMEOUT_CYCLES(DEADLINE),.T_WR(WRITE_DELAY)) dut(
        .clk(clk),.rstn(rstn),.pluse(trigger),.device_id(8'h56),.w_r(1'b1),
        .byte_len(4'd1),.addr({ADDR_BYTES*8{1'b0}}),.data_in(8'ha5),
        .busy(busy),.byte_over(over),.data_out(read_data),.scl(scl),.scl_in(1'b1),
        .sda_in(1'b1),.sda_out(data_bit),.sda_out_en(oe),
        .transaction_failed(failed),.error_code(code));
    initial begin
        repeat(5) @(negedge clk); rstn=1;
        repeat(5) @(negedge clk); trigger=1; @(negedge clk); trigger=0;
        repeat(20) @(negedge clk);
        if(!failed || code!==4'he || busy || over || scl!==1 || oe!==0)
            $fatal(1,"Invalid configuration was not rejected");
        done=1;
    end
endmodule

module iic_timing_parameter_probe(output reg done=0);
    iic_dri_checked #(.CLK_FRE(50_000_000)) fast50();
    iic_dri_checked #(.CLK_FRE(100_000_000),.IIC_FREQ(100_000)) standard100();
    iic_dri_checked #(.CLK_FRE(10_500_000),.T_WR(1)) fractional_us();
    initial begin
        #1;
        if(fast50.QUARTER_CYCLES!=33 || standard100.QUARTER_CYCLES!=470
           || fractional_us.WR_DELAY!=11) $fatal(1,"Timing parameter arithmetic truncated or overflowed");
        done=1;
    end
endmodule
