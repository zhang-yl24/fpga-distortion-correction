`timescale 1ns/1ps
// Independent wire slave: table fixture oracle, real quarter=68 controller.
module upright_sensor_case #(parameter UNIT=0, CHECK_WRITES=1, DYNAMIC_PAD_MASK=0)
    (output reg complete=0);
    reg clk=0; always #18.519 clk=~clk;
    reg rst_n=0,slave_low=0;
    tri1 cam_rst_n,cam_scl,cam_sda;
    assign cam_sda=slave_low ? 1'b0:1'bz;
    reg [15:0] trial_pad_mask=16'h1234;
    wire [15:0] sensor_id,failed_address;
    wire ready,failed; wire [7:0] error_code,observed_value,expected_value;
    wire [8:0] commands_written,verified_write_noacks;
    ov5640_cadence_upright_init #(.RESET_CYCLES(8),.WAIT_CYCLES(12),.MS_CYCLES(2),
        .I2C_QUARTER_CYCLES(68),.I2C_TIMEOUT_CYCLES(1350000),
        .CHECK_WRITES(CHECK_WRITES),.DYNAMIC_PAD_MASK(DYNAMIC_PAD_MASK)) dut(.*);
    reg [31:0] base_words[0:263];
    reg [7:0] registers[0:65535];
    integer trace_file,summary_file,case_id=-1;
    integer core_cycles=0,writes=0,transactions=0,starts=0;
    integer checked_periods=0,last_tx_rise=0;
    integer delay_entries=0,retry_delays=0,orientation0_reads=0,orientation1_reads=0;
    reg previous_tx_rise=0,previous_delay=0,allow_ready=0,terminal_seen=0;
    reg [1:0] previous_byte=0;
    reg [31:0] required_delay;
    always @(posedge clk) core_cycles=core_cycles+1;
    always @(negedge clk) begin
        if(rst_n) begin
            if(ready && !allow_ready) $fatal(1,"Premature ready unit=%0d case=%0d",UNIT,case_id);
            if(ready && failed) $fatal(1,"Conflicting terminal flags");
            if(dut.state==9 && !previous_delay) begin
                if(dut.command_index>263) $fatal(1,"Invalid command index");
                required_delay=base_words[dut.command_index][7:0]*2;
                if(dut.command_index==263 && dut.verify_retry) begin
                    required_delay=1000; retry_delays=retry_delays+1;
                end
                if(dut.delay_cycles!==required_delay)
                    $fatal(1,"Changed delay unit=%0d case=%0d index=%0d got=%0d expected=%0d",
                        UNIT,case_id,dut.command_index,dut.delay_cycles,required_delay);
                delay_entries=delay_entries+1;
            end
            previous_delay=(dut.state==9);
        end else previous_delay=0;
    end
    always @(negedge cam_sda) if(rst_n && cam_scl===1) begin
        if(terminal_seen) $fatal(1,"Bus activity after terminal unit=%0d case=%0d",UNIT,case_id);
        starts=starts+1;
    end
    always @(posedge cam_scl) begin
        #1;
        if(rst_n && dut.bus.state==5) begin
            if(dut.bus.bit_index<7 && previous_tx_rise && previous_byte==dut.bus.byte_index) begin
                if(core_cycles-last_tx_rise!=274)
                    $fatal(1,"Quarter68 transmit period changed: %0d",core_cycles-last_tx_rise);
                checked_periods=checked_periods+1;
            end
            last_tx_rise=core_cycles; previous_tx_rise=1;previous_byte=dut.bus.byte_index;
        end else previous_tx_rise=0;
    end
    function automatic bit originally_checkable(input [15:0] address);
        case(address)
            16'h3103,16'h3108,16'h3034,16'h3035,16'h3036,16'h3037,
            16'h3017,16'h3018,16'h300e,16'h3808,16'h3809,16'h380a,16'h380b,
            16'h4300,16'h501f,16'h4740: originally_checkable=1;
            default: originally_checkable=0;
        endcase
    endfunction
    function automatic [15:0] verify_address(input integer index);
        case(index)
            0:verify_address=16'h3808; 1:verify_address=16'h3809;
            2:verify_address=16'h380a; 3:verify_address=16'h380b;
            4:verify_address=16'h4300; 5:verify_address=16'h501f;
            6:verify_address=16'h4740; 7:verify_address=16'h3820;
            8:verify_address=16'h3821;
            default:verify_address=16'hffff;
        endcase
    endfunction
    function automatic [7:0] expected_write(input integer index);
        reg [15:0] address;
        begin
            address=base_words[index][31:16];expected_write=base_words[index][15:8];
            if(address==16'h3820) expected_write=8'h00;
            if(address==16'h3821) expected_write=8'h06;
            if(DYNAMIC_PAD_MASK && address==16'h3017) expected_write=trial_pad_mask[15:8];
            if(DYNAMIC_PAD_MASK && address==16'h3018) expected_write=trial_pad_mask[7:0];
        end
    endfunction
    task automatic get_start;
        begin do @(negedge cam_sda); while(cam_scl!==1); end
    endtask
    task automatic get_stop;
        begin do @(posedge cam_sda); while(cam_scl!==1); end
    endtask
    task automatic get_byte(output reg [7:0] value,input bit ack);
        begin
            value=0;
            repeat(8) begin @(posedge cam_scl);value={value[6:0],cam_sda};end
            @(negedge cam_scl);slave_low=ack;
            @(posedge cam_scl);@(negedge cam_scl);slave_low=0;
        end
    endtask
    task automatic expect_byte(input [7:0] expected,input bit ack);
        reg [7:0] value;
        begin
            get_byte(value,ack);
            if(value!==expected) $fatal(1,"Wire byte unit=%0d case=%0d got=%h expected=%h",UNIT,case_id,value,expected);
        end
    endtask
    task automatic reply(input [7:0] value);
        begin
            for(integer i=7;i>=0;i=i-1) begin
                slave_low=!value[i];@(posedge cam_scl);@(negedge cam_scl);
            end
            slave_low=0;@(posedge cam_scl);
            if(cam_sda!==1) $fatal(1,"Master read must end with NACK");
            @(negedge cam_scl);
        end
    endtask
    // phase: 0 ID, 1 immediate, 2 pre-final-start, 3 post-start, 4 retry.
    task automatic read_register(input [15:0] address,input [7:0] value,
                                  input integer phase,input bit read_ack);
        integer began;
        begin
            get_start();began=core_cycles;expect_byte(8'h78,read_ack);
            if(read_ack) begin
                expect_byte(address[15:8],1);expect_byte(address[7:0],1);
                get_start();expect_byte(8'h79,1);reply(value);
            end
            get_stop();transactions=transactions+1;
            if(address==16'h3820) orientation0_reads=orientation0_reads+1;
            if(address==16'h3821) orientation1_reads=orientation1_reads+1;
            $fdisplay(trace_file,"%0d,R,%04h,%02h,%0d,%0d,-1,%0d,%0d",case_id,address,value,read_ack,phase,began,core_cycles);
        end
    endtask
    task automatic write_register(input integer index,input bit data_ack,
                                   input bit corrupt_read,input bit read_ack);
        reg [15:0] address;reg [7:0] value;integer began;
        begin
            address=base_words[index][31:16];value=expected_write(index);
            if(writes!=index) $fatal(1,"Write order changed");
            get_start();began=core_cycles;expect_byte(8'h78,1);
            expect_byte(address[15:8],1);expect_byte(address[7:0],1);expect_byte(value,data_ack);
            get_stop();registers[address]=value;writes=writes+1;transactions=transactions+1;
            $fdisplay(trace_file,"%0d,W,%04h,%02h,%0d,0,%0d,%0d,%0d",case_id,address,value,data_ack,index,began,core_cycles);
            if(!data_ack || (CHECK_WRITES && originally_checkable(address)) ||
               address==16'h3820 || address==16'h3821)
                read_register(address,corrupt_read ? (value^8'h01):value,1,read_ack);
        end
    endtask
    task automatic identify;
        begin read_register(16'h300a,8'h56,0,1);read_register(16'h300b,8'h40,0,1);end
    endtask
    task automatic verify_prefix(input integer phase,input integer bad_index);
        reg [15:0] address;
        begin
            for(integer i=0;i<9;i=i+1) begin
                if(bad_index<0 || i<=bad_index) begin
                    address=verify_address(i);
                    read_register(address,i==bad_index ? (registers[address]^8'h01):registers[address],phase,1);
                end
            end
        end
    endtask
    task automatic reset_case(input integer n);
        begin
            @(negedge clk);rst_n=0;slave_low=0;terminal_seen=0;allow_ready=0;
            case_id=n;writes=0;transactions=0;starts=0;checked_periods=0;
            delay_entries=0;retry_delays=0;orientation0_reads=0;orientation1_reads=0;
            previous_tx_rise=0;previous_delay=0;
            repeat(5) @(negedge clk);rst_n=1;
        end
    endtask
    task automatic finish_case(input bit success,input [7:0] wanted_error,
        input [15:0] wanted_address,input integer written,input integer noacks,
        input integer retries,input [7:0] wanted_observed,input [7:0] wanted_expected);
        integer saved_starts;
        begin
            if(success) allow_ready=1;
            wait(ready || failed);@(negedge clk);
            if(ready!==success || failed===success || error_code!==wanted_error ||
               commands_written!=written || verified_write_noacks!=noacks ||
               delay_entries!=written+retries || retry_delays!=retries)
                $fatal(1,"Status unit=%0d case=%0d ready=%b failed=%b err=%h commands=%0d noacks=%0d delay=%0d retry=%0d",
                    UNIT,case_id,ready,failed,error_code,commands_written,verified_write_noacks,delay_entries,retry_delays);
            if(!success && (failed_address!==wanted_address ||
                (wanted_error!=8'h61 && wanted_error!=8'h20 &&
                 (observed_value!==wanted_observed || expected_value!==wanted_expected))))
                $fatal(1,"Fault details unit=%0d case=%0d address=%h observed=%h expected=%h",
                    UNIT,case_id,failed_address,observed_value,expected_value);
            terminal_seen=1;saved_starts=starts;repeat(2000) @(negedge clk);
            if(ready!==success || failed===success || starts!=saved_starts) $fatal(1,"Terminal state not stable");
            if(checked_periods<40) $fatal(1,"Missing SCCB timing coverage");
            $fdisplay(summary_file,"%0d,%0d,%0d,%0d,%02h,%04h,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d",
                UNIT,case_id,ready,failed,error_code,failed_address,commands_written,writes,transactions,
                delay_entries,retry_delays,checked_periods,verified_write_noacks,starts,orientation0_reads,orientation1_reads);
            $display("UPRIGHT_CASE_PASS unit=%0d case=%0d writes=%0d commands=%0d transactions=%0d error=%h",
                UNIT,case_id,writes,commands_written,transactions,error_code);
        end
    endtask
    task automatic full_prefix(input bit nack_orientation);
        begin
            identify();
            for(integer i=0;i<263;i=i+1) write_register(i,!(nack_orientation && i==41),0,1);
        end
    endtask
    initial begin
        $readmemh("base-commands.mem",base_words);
        trace_file=$fopen($sformatf("trace-%0d.csv",UNIT),"w");
        summary_file=$fopen($sformatf("cases-%0d.csv",UNIT),"w");
        $fdisplay(trace_file,"case,kind,address,value,ack,phase,index,start,stop");
        $fdisplay(summary_file,"unit,case,ready,failed,error,address,written,writes,transactions,delay_entries,retry_delays,periods,noacks,starts,read3820,read3821");
        #100;
        reset_case(0);full_prefix(UNIT==1);verify_prefix(2,-1);write_register(263,1,0,1);
        verify_prefix(3,-1);finish_case(1,0,0,264,UNIT==1 ? 1:0,0,0,0);
        // Both addresses independently reject mismatch even with CHECK_WRITES=0.
        reset_case(1);identify();
        for(integer i=0;i<41;i=i+1) write_register(i,1,i==40,1);
        finish_case(0,8'h70,16'h3820,40,0,0,8'h01,8'h00);
        reset_case(2);identify();
        for(integer i=0;i<42;i=i+1) write_register(i,1,i==41,1);
        finish_case(0,8'h70,16'h3821,41,0,0,8'h07,8'h06);
        if(UNIT==0) begin
            // Only before final start: index245's earlier 3008=02 is preserved.
            reset_case(3);full_prefix(0);verify_prefix(2,7);
            finish_case(0,8'h51,16'h3820,263,0,0,8'h01,8'h00);
            reset_case(4);full_prefix(0);verify_prefix(2,-1);write_register(263,1,0,1);
            verify_prefix(3,7);verify_prefix(4,-1);
            finish_case(1,0,0,264,0,1,0,0);
            reset_case(5);full_prefix(0);verify_prefix(2,-1);write_register(263,1,0,1);
            verify_prefix(3,8);verify_prefix(4,8);
            finish_case(0,8'h50,16'h3821,264,0,1,8'h07,8'h06);
            reset_case(6);identify();
            for(integer i=0;i<42;i=i+1) write_register(i,1,0,i!=41);
            finish_case(0,8'h61,16'h3821,41,0,0,0,0);
            reset_case(7);read_register(16'h300a,8'h56,0,1);read_register(16'h300b,8'h42,0,1);
            finish_case(0,8'h20,0,0,0,0,0,0);
        end
        @(negedge clk);rst_n=0;$fclose(trace_file);$fclose(summary_file);complete=1;
    end
endmodule
module tb_ov5640_cadence_upright;
    wire complete_checked,complete_mandatory;
    upright_sensor_case #(.UNIT(0),.CHECK_WRITES(1),.DYNAMIC_PAD_MASK(0)) checked(complete_checked);
    upright_sensor_case #(.UNIT(1),.CHECK_WRITES(0),.DYNAMIC_PAD_MASK(1)) mandatory(complete_mandatory);
    initial begin wait(complete_checked && complete_mandatory);
        $display("OV5640_CADENCE_UPRIGHT_PASS cases=11 quarter=68 digital_only=1");$finish;end
    initial begin repeat(30) #100000000;$fatal(1,"Upright line-model watchdog");end
endmodule
