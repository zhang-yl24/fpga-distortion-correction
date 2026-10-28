`timescale 1ns/1ps
// Digital line model only. Faults are driven through open-drain SCL/SDA;
// neither controller error nor the init FSM is forced.
module tb_ov5640_cadence_diagnostic_init;
    reg clk=0; always #18.519 clk=~clk;
    reg rst_n=0;
    tri1 cam_rst_n,cam_scl,cam_sda;
    reg slave_low=0,slave_clock_low=0;
    assign cam_sda=slave_low ? 1'b0:1'bz;
    assign cam_scl=slave_clock_low ? 1'b0:1'bz;
    reg [15:0] trial_pad_mask=16'h7ff0;
    wire [15:0] sensor_id,failed_address;
    wire ready,failed; wire [7:0] error_code,observed_value,expected_value;
    wire [8:0] commands_written,verified_write_noacks;
    wire diag3018_write_issued,diag3018_write_completed;
    wire [3:0] diag3018_write_bus_error,diag3018_read_bus_error;
    wire diag3018_final_data_noack,diag3018_noack_pending;
    wire diag3018_read_issued,diag3018_read_completed;
    wire [7:0] diag3018_read_value;
    wire diag3018_read_value_valid,diag3018_read_equal;
    wire [2:0] diagnostic_probe_attempted,diagnostic_probe_completed,diagnostic_probe_value_valid;
    wire [11:0] diagnostic_probe_bus_errors;
    wire [23:0] diagnostic_probe_values;
    wire [1:0] diagnostic_probe_count; wire diagnostic_probe_done;
    ov5640_cadence_diagnostic_init #(.RESET_CYCLES(8),.WAIT_CYCLES(12),.MS_CYCLES(2),
        .DYNAMIC_PAD_MASK(1)) dut(.*);

    // Golden original runs on the same resolved wires until failure. Afterwards
    // it remains FAILED and releases its controller while the new observer reads.
    wire [15:0] old_sensor_id,old_failed_address;
    wire old_ready,old_failed; wire [7:0] old_error_code,old_observed_value,old_expected_value;
    wire [8:0] old_commands_written,old_verified_write_noacks;
    ov5640_cadence_trial_init #(.RESET_CYCLES(8),.WAIT_CYCLES(12),.MS_CYCLES(2),
        .DYNAMIC_PAD_MASK(1)) golden(.clk(clk),.rst_n(rst_n),.cam_rst_n(cam_rst_n),
        .cam_scl(cam_scl),.cam_sda(cam_sda),.trial_pad_mask(trial_pad_mask),
        .sensor_id(old_sensor_id),.failed_address(old_failed_address),.ready(old_ready),
        .failed(old_failed),.error_code(old_error_code),.commands_written(old_commands_written),
        .verified_write_noacks(old_verified_write_noacks),.observed_value(old_observed_value),
        .expected_value(old_expected_value));
    integer case_id=-1,writes=0,probe_requests=0,trace_file;
    integer core_cycles=0,last_tx_rise=0,checked_periods=0;
    reg previous_tx_rise=0;reg [1:0] previous_byte=0;
    reg [7:0] registers[0:65535];
    always @(posedge clk)core_cycles=core_cycles+1;
    always @(negedge clk)if(rst_n)begin
        if({ready,failed,sensor_id,error_code,failed_address,commands_written,
            verified_write_noacks,observed_value,expected_value} !==
           {old_ready,old_failed,old_sensor_id,old_error_code,old_failed_address,old_commands_written,
            old_verified_write_noacks,old_observed_value,old_expected_value})
            $fatal(1,"Legacy output diverged from original init, case %0d",case_id);
        if(dut.state!=13 && {dut.state,dut.trigger,dut.address,dut.read_mode,dut.write_data} !==
           {golden.state,golden.trigger,golden.address,golden.read_mode,golden.write_data})
            $fatal(1,"Original transaction ordering diverged, case %0d",case_id);
    end
    always @(posedge clk)if(rst_n)begin
        if(dut.trigger && dut.state==13)begin
            if(!dut.read_mode || probe_requests>=3 ||
               dut.address!==(probe_requests==0 ? 16'h300a:probe_requests==1 ? 16'h300b:16'h3018))
                $fatal(1,"Extra/mutating/out-of-order failed-state probe");
            probe_requests=probe_requests+1;
        end
        if(dut.done)$fdisplay(trace_file,"%0d,%0d,%04h,%0d,%01h,%02h,%0d",case_id,
            dut.state,dut.address,dut.read_mode,dut.bus_error,dut.read_data,diag3018_noack_pending);
    end
    always @(posedge cam_scl)begin
        #1;
        if(rst_n && dut.bus.state==5)begin
            if(dut.bus.bit_index<7 && previous_tx_rise && previous_byte==dut.bus.byte_index)begin
                if(core_cycles-last_tx_rise!=274)$fatal(1,"Quarter68 changed: period %0d",core_cycles-last_tx_rise);
                checked_periods=checked_periods+1;
            end
            last_tx_rise=core_cycles;previous_tx_rise=1;previous_byte=dut.bus.byte_index;
        end else previous_tx_rise=0;
    end
    task automatic get_start;
        begin do @(negedge cam_sda); while(cam_scl!==1); end
    endtask
    task automatic get_byte(output reg [7:0] value,input bit ack);
        begin
            value=0;
            repeat(8)begin @(posedge cam_scl);value={value[6:0],cam_sda};end
            @(negedge cam_scl);slave_low=ack;
            @(posedge cam_scl);@(negedge cam_scl);slave_low=0;
        end
    endtask
    task automatic expect_byte(input [7:0] expected,input bit ack);
        reg [7:0] value;
        begin get_byte(value,ack);if(value!==expected)$fatal(1,"Case%0d wire byte %h vs %h",case_id,value,expected);end
    endtask
    task automatic reply(input [7:0] value);
        begin
            for(integer i=7;i>=0;i=i-1)begin
                slave_low=!value[i];@(posedge cam_scl);@(negedge cam_scl);
            end
            slave_low=0;@(posedge cam_scl);
            if(cam_sda!==1)$fatal(1,"Master must terminate read with NACK");
            @(negedge cam_scl);
        end
    endtask
    // phase1: first 0x78 address NACK; phase2: repeated-start 0x79 NACK.
    task automatic register_read(input [15:0] address,input [7:0] value,input integer phase);
        begin
            get_start();expect_byte(8'h78,phase!=1);
            if(phase!=1)begin
                expect_byte(address[15:8],1);expect_byte(address[7:0],1);
                get_start();expect_byte(8'h79,phase!=2);
                if(phase!=2)reply(value);
            end
        end
    endtask
    task automatic register_write(input bit data_ack,input bit bad_device,input integer read_phase,input bit bad_value);
        reg [7:0] hi,lo,value;
        begin
            get_start();expect_byte(8'h78,!bad_device);
            if(!bad_device)begin
                get_byte(hi,1);get_byte(lo,1);get_byte(value,data_ack);
                // Sensor model accepts the byte even when its final Don't-Care
                // level is high; host must still verify it, as in the old policy.
                registers[{hi,lo}]=value;writes=writes+1;
                if(!data_ack || dut.checkable_write({hi,lo}))
                    register_read({hi,lo},bad_value ? 8'h00:value,read_phase);
            end
        end
    endtask
    task automatic reset_case(input integer n);
        begin
            @(negedge clk);rst_n=0;slave_low=0;slave_clock_low=0;
            writes=0;probe_requests=0;case_id=n;registers[16'h3018]=8'ha5;
            repeat(5)@(negedge clk);rst_n=1;
        end
    endtask
    task automatic prefix;
        begin
            register_read(16'h300a,8'h56,0);register_read(16'h300b,8'h40,0);
            repeat(262)register_write(1,0,0,0);
        end
    endtask
    task automatic verify_seven;
        begin
            register_read(16'h3808,registers[16'h3808],0);register_read(16'h3809,registers[16'h3809],0);
            register_read(16'h380a,registers[16'h380a],0);register_read(16'h380b,registers[16'h380b],0);
            register_read(16'h4300,registers[16'h4300],0);register_read(16'h501f,registers[16'h501f],0);
            register_read(16'h4740,registers[16'h4740],0);
        end
    endtask
    task automatic success_tail(input bit final_nack);
        begin
            verify_seven();register_write(1,0,0,0);verify_seven();wait(ready);#1;
            if(failed || commands_written!==264 || writes!=264 || sensor_id!==16'h5640 ||
               verified_write_noacks!=={8'b0,final_nack} ||
               !diag3018_write_issued || !diag3018_write_completed || !diag3018_read_issued || !diag3018_read_completed ||
               diag3018_write_bus_error!==(final_nack ? 4'h4:4'h0) ||
               diag3018_final_data_noack!==final_nack || diag3018_noack_pending ||
               diag3018_read_bus_error!=0 || !diag3018_read_value_valid || !diag3018_read_equal ||
               diag3018_read_value!==8'hf0 || diagnostic_probe_count!=0 || probe_requests!=0)
                $fatal(1,"Success/verified final data-high accounting incorrect");
            if(registers[16'h3017]!==8'h7f || registers[16'h3018]!==8'hf0 || registers[16'h3035]!==8'h21 ||
               registers[16'h3036]!==8'h60 || registers[16'h3037]!==8'h13 || registers[16'h3108]!==8'h01 ||
               registers[16'h3808]!==8'h02 || registers[16'h3809]!==8'h80 || registers[16'h380a]!==8'h01 ||
               registers[16'h380b]!==8'he0 || registers[16'h4300]!==8'h6f || registers[16'h501f]!==8'h01 ||
               registers[16'h4740]!==8'h23 || registers[16'h3008]!==8'h02)
                $fatal(1,"Original mask/PLL/VGA/format changed");
            repeat(2000)@(negedge clk);
            if(diagnostic_probe_attempted!=0 || diagnostic_probe_done)$fatal(1,"Probed successful init");
        end
    endtask
    task automatic check_original_fault(input [7:0] err,input [3:0] write_err,input bit pending,
                                        input bit read_issued,input [3:0] read_err,input bit value_valid);
        begin
            wait(failed);#1;
            if(ready || error_code!==err || failed_address!==16'h3018 || commands_written!==262 ||
               verified_write_noacks!=0 || !diag3018_write_issued || !diag3018_write_completed ||
               diag3018_write_bus_error!==write_err || diag3018_final_data_noack!==(write_err==4) ||
               diag3018_noack_pending!==pending || diag3018_read_issued!==read_issued ||
               diag3018_read_completed!==read_issued || diag3018_read_bus_error!==read_err ||
               diag3018_read_value_valid!==value_valid || diag3018_read_equal)
                $fatal(1,"Case%0d failed/write/read/pending evidence conflated",case_id);
        end
    endtask
    task automatic followup(input bit middle_nack,input bit timeout_first);
        begin
            if(timeout_first)begin
                // Hold SCL before the failed-state request reaches the controller.
                slave_clock_low=1;
                wait(dut.done && dut.bus_error==15);@(negedge clk);slave_clock_low=0;
            end else register_read(16'h300a,8'h56,0);
            register_read(16'h300b,8'h40,middle_nack ? 1:0);
            register_read(16'h3018,registers[16'h3018],0);
            wait(diagnostic_probe_done);repeat(2000)@(negedge clk);
            if(!failed || ready || probe_requests!=3 || diagnostic_probe_count!==3 ||
               diagnostic_probe_attempted!==7 || diagnostic_probe_completed!==7 ||
               diagnostic_probe_value_valid!==(timeout_first ? 3'b110:middle_nack ? 3'b101:3'b111) ||
               diagnostic_probe_bus_errors!==(timeout_first ? 12'h00f:middle_nack ? 12'h010:12'h000) ||
               diagnostic_probe_values[23:16]!==registers[16'h3018])
                $fatal(1,"Probe limit/results/fault retention incorrect, case%0d",case_id);
            if(!timeout_first && diagnostic_probe_values[7:0]!==8'h56)$fatal(1,"Probe high ID not recorded");
            if(!middle_nack && diagnostic_probe_values[15:8]!==8'h40)$fatal(1,"Probe low ID not recorded");
        end
    endtask
    initial begin
        trace_file=$fopen("diagnostic-transactions.csv","w");
        $fdisplay(trace_file,"case,state,address,read,bus_error,raw_read_value,pending_before_event");
        #1;
        if(dut.I2C_QUARTER_CYCLES!=68 || dut.bus.QUARTER_CYCLES!=68 ||
           dut.I2C_TIMEOUT_CYCLES!=1350000 || dut.CHECK_WRITES!=1 || trial_pad_mask!==16'h7ff0)
            $fatal(1,"Frozen full-mask baseline parameters changed");
        #100;reset_case(0);prefix();register_write(1,0,0,0);success_tail(0);
        $display("PASS_CASE original_success_full_264");
        reset_case(1);prefix();register_write(0,0,0,0);success_tail(1);
        $display("PASS_CASE final_data_noack_equal_readback");
        reset_case(2);prefix();register_write(0,0,1,0);
        check_original_fault(8'h61,4,1,1,1,0);followup(1,0);
        if(!diag3018_noack_pending || diag3018_read_value_valid || observed_value!==0)
            $fatal(1,"Failed read or later probe incorrectly resolves pending write");
        $display("PASS_CASE final_data_noack_then_read_address_nack");
        reset_case(3);prefix();register_write(0,0,0,1);
        check_original_fault(8'h70,4,1,1,0,1);followup(0,0);
        if(!diag3018_noack_pending || !diag3018_read_value_valid || diag3018_read_equal ||
           diag3018_read_value!==0 || observed_value!==0 || error_code!==8'h70)
            $fatal(1,"Wrong original value repaired by later equal probe");
        $display("PASS_CASE final_data_noack_then_wrong_valid_value");
        reset_case(4);prefix();register_write(1,1,0,0);
        check_original_fault(8'h31,1,0,0,0,0);followup(0,0);
        if(writes!=262 || diagnostic_probe_values[23:16]!==8'ha5)
            $fatal(1,"Write device NACK fabricated data delivery");
        $display("PASS_CASE write_device_address_nack");
        reset_case(5);prefix();register_write(1,0,1,0);
        check_original_fault(8'h61,0,0,1,1,0);followup(0,0);
        $display("PASS_CASE acknowledged_write_then_read_address_nack");
        reset_case(6);prefix();register_write(1,0,2,0);
        check_original_fault(8'h64,0,0,1,4,0);followup(0,1);
        if(error_code!==8'h64 || diag3018_read_bus_error!==4 || diag3018_final_data_noack)
            $fatal(1,"Read-device error4 confused with write-final-data error4");
        $display("PASS_CASE read_phase_device_nack_and_bounded_probe_timeout");
        if(checked_periods<1000)$fatal(1,"Insufficient real SCL periods");
        $display("PASS diagnostic init: seven real-controller line-model cases; legacy miter; quarter68/full7FF0; three read-only probes maximum; no hardware or RAW authorization.");
        $fclose(trace_file);$finish;
    end
    initial begin #(64'd1500000000);$fatal(1,"Bounded diagnostic init simulation timeout");end
endmodule
