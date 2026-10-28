`timescale 1ns/1ps
// Real reg16_i2c and resolved open-drain lines; no forced controller result.
module tb_ov5640_rgb565_720_init;
    reg clk=0;always #18.519 clk=~clk;
    reg rst_n=0,slave_low=0;
    tri1 cam_rst_n,cam_scl,cam_sda;
    assign cam_sda=slave_low ? 1'b0:1'bz;
    wire [15:0] sensor_id,failed_address;
    wire configured,failed,observed_valid,final_wake_verified;
    wire [7:0] error_code,observed_value,expected_value;
    wire [3:0] last_bus_error;
    wire [9:0] action_index,failed_action,writes_completed,verified_write_noacks;
    ov5640_rgb565_720_init #(.RESET_CYCLES(8),.WAIT_CYCLES(12),.MS_CYCLES(2)) dut(.*);
    reg [7:0] registers[0:65535];
    integer scenario=-1,wake_count=0,bus_writes=0,bus_reads=0,clock_writes=0,trace_file;
    reg nack_used=0;
    task automatic defaults;
        begin
            for(integer n=0;n<65536;n=n+1)registers[n]=0;
            registers[16'h300a]=8'h56;registers[16'h300b]=8'h40;registers[16'h3008]=8'h02;
            registers[16'h3034]=8'h1a;registers[16'h3035]=8'h11;registers[16'h3036]=8'h69;
            registers[16'h3037]=8'h03;registers[16'h3039]=8'h35;registers[16'h3103]=8'h03;registers[16'h3108]=1;
        end
    endtask
    task automatic get_start;
        begin do @(negedge cam_sda);while(cam_scl!==1);end
    endtask
    task automatic get_byte(output reg [7:0] value,input bit ack);
        begin
            value=0;repeat(8)begin @(posedge cam_scl);value={value[6:0],cam_sda};end
            @(negedge cam_scl);slave_low=ack;@(posedge cam_scl);@(negedge cam_scl);slave_low=0;
        end
    endtask
    task automatic expect_byte(input [7:0] expected,input bit ack);
        reg [7:0] value;
        begin get_byte(value,ack);if(value!==expected)$fatal(1,"720 wire byte %h != %h",value,expected);end
    endtask
    task automatic reply(input [7:0] value);
        begin
            for(integer b=7;b>=0;b=b-1)begin slave_low=!value[b];@(posedge cam_scl);@(negedge cam_scl);end
            slave_low=0;@(posedge cam_scl);if(cam_sda!==1)$fatal(1,"Missing master read NACK");@(negedge cam_scl);
        end
    endtask
    task automatic sensor_transaction;
        reg read_transaction,device_nack,data_nack;
        reg [15:0] expected_address,a;
        reg [7:0] hi,lo,value,returned;
        integer prediv,mult;
        begin
            get_start();read_transaction=dut.read_mode;expected_address=dut.address;
            device_nack=(scenario==1 && read_transaction && expected_address==16'h3018) ||
                (scenario==4 && read_transaction && expected_address==16'h3035 && action_index>=dut.MODE_POSTFLIGHT);
            expect_byte(8'h78,!device_nack);
            if(!device_nack)begin
                get_byte(hi,1);get_byte(lo,1);a={hi,lo};
                if(a!==expected_address)$fatal(1,"Wire register address differs from request");
                if(read_transaction)begin
                    bus_reads=bus_reads+1;get_start();expect_byte(8'h79,1);returned=registers[a];
                    if(scenario==2 && a==16'h3036 && clock_writes==0)returned=8'h68;
                    if(scenario==3 && a==16'h3808 && action_index>=dut.MODE_PREFLIGHT && action_index<dut.MODE_WAKE)returned=8'h04;
                    if(scenario==5 && a==16'h3039 && nack_used)returned=returned^8'h01;
                    reply(returned);
                end else begin
                    data_nack=(!nack_used && ((scenario==0 && a==16'h3036) || (scenario==5 && a==16'h3039)));
                    get_byte(value,!data_nack);if(data_nack)nack_used=1;
                    bus_writes=bus_writes+1;
                    if(a==16'h3008 && value[7])defaults();else registers[a]=value;
                    if(a==16'h3008 && !value[7] && !value[6])begin
                        wake_count=wake_count+1;
                        if(action_index!=dut.MODE_WAKE || wake_count!=1)$fatal(1,"Early/repeated wake escaped source filtering");
                    end
                    if(a==16'h3036 || a==16'h3037)begin
                        clock_writes=clock_writes+1;
                        if(registers[16'h3103][1] || !registers[16'h3008][6] || !registers[16'h3039][7])
                            $fatal(1,"PLL written before confirmed pad/standby/bypass isolation");
                        prediv=registers[16'h3037]&15;mult=registers[16'h3036];
                        if(prediv==0 || 27000000.0*mult/prediv>800000000.0)$fatal(1,"Controlled changed-state VCO exceeds800MHz model");
                        if(a==16'h3036 && value!=84)$fatal(1,"Legacy96/105 multiplier was written");
                    end
                end
            end
        end
    endtask
    initial forever sensor_transaction();
    always @(posedge clk)if(rst_n && dut.done)$fdisplay(trace_file,"%0d,%0d,%04h,%0d,%01h,%02h",scenario,
        action_index,dut.address,dut.read_mode,dut.bus_error,dut.read_data);
    task automatic reset_case(input integer n);
        begin
            @(negedge clk);rst_n=0;slave_low=0;scenario=n;wake_count=0;bus_writes=0;bus_reads=0;clock_writes=0;nack_used=0;
            defaults();repeat(5)@(negedge clk);rst_n=1;
        end
    endtask
    task automatic fault_case(input integer n,input [7:0] code,input [15:0] address,input integer wakes);
        reg [7:0] saved_code;reg [15:0] saved_address;integer completed;
        begin
            reset_case(n);wait(failed);#1;
            if(configured || error_code!==code || failed_address!==address || wake_count!=wakes)
                $fatal(1,"Failed720 config not quarantined case=%0d code=%h address=%h wake=%0d",n,error_code,failed_address,wake_count);
            saved_code=error_code;saved_address=failed_address;completed=bus_writes+bus_reads;
            repeat(2000)@(negedge clk);
            if(configured || !failed || saved_code!==error_code || saved_address!==failed_address || bus_writes+bus_reads!=completed)
                $fatal(1,"Sticky failure retried or changed");
        end
    endtask
    initial begin
        trace_file=$fopen("rgb565720-transactions.csv","w");$fdisplay(trace_file,"case,action,address,read,error,raw_value");
        #1;if(dut.I2C_QUARTER_CYCLES!=68 || dut.I2C_TIMEOUT_CYCLES!=1350000)$fatal(1,"Baseline bus timings changed");
        #100;reset_case(0);wait(configured);#1;
        if(failed || sensor_id!==16'h5640 || !final_wake_verified || wake_count!=1 || verified_write_noacks!=1 || action_index!=dut.MODE_ACTIONS-1)
            $fatal(1,"Complete720 action/readback status incorrect");
        if(registers[16'h3034]!==8'h18 || registers[16'h3035]!==8'h40 || registers[16'h3036]!==8'h54 ||
           registers[16'h3037]!==8'h13 || registers[16'h3108]!==1 || registers[16'h3039]!==8'h35 ||
           {registers[16'h3808],registers[16'h3809]}!==16'd1280 || {registers[16'h380a],registers[16'h380b]}!==16'd720 ||
           {registers[16'h380c],registers[16'h380d]}!==16'd1892 || {registers[16'h380e],registers[16'h380f]}!==16'd740 ||
           registers[16'h4300]!==8'h6f || registers[16'h501f]!==1 || registers[16'h460c]!==8'h20 || registers[16'h3824]!==4 ||
           registers[16'h3017]!==8'h7f || registers[16'h3018]!==8'hf0 || registers[16'h4740]!==8'h23 ||
           registers[16'h3a09]!==8'd110 || registers[16'h3a0b]!==8'd91 || registers[16'h3a0e]!==6 || registers[16'h3a0d]!==8)
            $fatal(1,"Complete720 model geometry/clock/banding/RGB/pad/read-preserve differs");
        $display("PASS_CASE complete720_readback_unique_wake_rmw_and_verified_data_high");
        fault_case(1,8'h61,16'h3018,0);
        if(observed_valid)$fatal(1,"Read-address NACK00 is not a value");
        $display("PASS_CASE pad_read_address_nack_no_wake");
        fault_case(2,8'h50,16'h3036,0);
        if(clock_writes!=0)$fatal(1,"Changed PLL after default read mismatch");
        $display("PASS_CASE initial_clock_default_mismatch_no_pll_writes");
        fault_case(3,8'h50,16'h3808,0);
        $display("PASS_CASE preflight_geometry_mismatch_no_wake");
        fault_case(4,8'h41,16'h3035,1);
        if(!final_wake_verified)$fatal(1,"Post-wake test never passed wake readback");
        $display("PASS_CASE postwake_read_nack_never_configured");
        fault_case(5,8'h70,16'h3039,0);
        if(!observed_valid || observed_value[7]!==expected_value[7] || observed_value===expected_value || verified_write_noacks!=0)
            $fatal(1,"Masked-only match excused RMW final-data high");
        $display("PASS_CASE masked_rmw_match_cannot_excuse_fullbyte_noack");
        $display("PASS RGB565720 init: complete403 actions, real reg16_i2c lines, pre6-mult84-pre3, full controlled readbacks, one final wake and sticky faults; no PCLK/line freshness or hardware admission.");
        $fclose(trace_file);$finish;
    end
    initial begin #(64'd3000000000);$fatal(1,"Bounded720 line-model timeout");end
endmodule
