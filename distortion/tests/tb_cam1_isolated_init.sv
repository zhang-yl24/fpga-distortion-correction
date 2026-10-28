`timescale 1ns/1ps
module tb_cam1_isolated_init;
    reg clk=0, clock_enabled=1; always #18.519 if(clock_enabled)clk=~clk;
    wire rst_n=dut.rst_n;
    tri1 cam_rst_n,cam_scl,cam_sda,cam2_hold_rst_n;
    reg slave_low=0;
    assign cam_sda=slave_low ? 1'b0:1'bz;
    wire [15:0] sensor_id,failed_address; wire ready,failed;
    wire [7:0] error_code; wire [8:0] commands_written;
    wire [8:0] verified_write_noacks;
    wire [7:0] observed_value,expected_value;
    reg [15:0] trial_pad_mask=16'h7ff0;
    // Instantiate the actual new board top. Only opaque vendor DDR/PLL/ADC are inert test stubs.
    raw_camera_capture_cam1_guarded_isolated dut(.clk_27m(clk),.cam_rst_n(cam_rst_n),
        .cam_scl(cam_scl),.cam_sda(cam_sda),.cam2_hold_rst_n(cam2_hold_rst_n),
        .uart_rxd(1'b1),.cam_pclk(1'b0),.cam_href(1'b1),.cam_vsync(1'b1),.cam_data(8'b0),
        .clk_p(1'b0),.clk_n(1'b1));
    defparam dut.camera.RESET_CYCLES=8,dut.camera.WAIT_CYCLES=12,dut.camera.MS_CYCLES=2;
    assign sensor_id=dut.sensor_id;assign failed_address=dut.camera_failed_address;
    assign ready=dut.camera_ready;assign failed=dut.camera_failed;assign error_code=dut.cam_errors;
    assign commands_written=dut.camera_writes;assign verified_write_noacks=dut.camera_noacks;
    assign observed_value=dut.camera_observed;assign expected_value=dut.camera_expected;
    always @(negedge clk) if(cam2_hold_rst_n!==1'b0)$fatal(1,"Actual board other-reset sink released/drove high");
    always @(cam2_hold_rst_n) if($time>0 && cam2_hold_rst_n!==1'b0)$fatal(1,"Actual board other-reset sink transition");
    reg [7:0] registers[0:65535];
    integer writes=0; reg corrupt=0, bad_pad=0, bad_pll=0, pad_address_nack=0;
    task automatic get_start;
        begin do @(negedge cam_sda); while(cam_scl!==1); end
    endtask
    task automatic get_byte(output reg [7:0] value,input bit ack);
        begin
            value=0;
            repeat(8) begin @(posedge cam_scl); value={value[6:0],cam_sda}; end
            @(negedge cam_scl); slave_low=ack;
            @(posedge cam_scl); @(negedge cam_scl); slave_low=0;
        end
    endtask
    task automatic expect_byte(input [7:0] expected,input bit ack);
        reg [7:0] value;
        begin get_byte(value,ack); if(value!==expected) $fatal(1,"SCCB byte %h vs %h",value,expected); end
    endtask
    task automatic reply(input [7:0] value);
        begin
            for(integer i=7;i>=0;i=i-1) begin
                slave_low=!value[i]; @(posedge cam_scl); @(negedge cam_scl);
            end
            slave_low=0; @(posedge cam_scl);
            if(cam_sda!==1) $fatal(1,"Read must end with NACK");
            @(negedge cam_scl);
        end
    endtask
    task automatic register_read(input [15:0] address,input [7:0] value);
        begin
            get_start();
            if(pad_address_nack && address==16'h3018)expect_byte(8'h78,0);
            else begin
                expect_byte(8'h78,1);expect_byte(address[15:8],1);expect_byte(address[7:0],1);
                get_start();expect_byte(8'h79,1);reply(value);
            end
        end
    endtask
    task automatic register_write(input bit acknowledge);
        reg [7:0] hi,lo,value;
        begin
            get_start(); expect_byte(8'h78,1); get_byte(hi,1);get_byte(lo,1);get_byte(value,acknowledge);
            if(acknowledge) begin
                registers[{hi,lo}]=value;writes=writes+1;
                if(dut.camera.checkable_write({hi,lo})) register_read({hi,lo},(bad_pad && {hi,lo}==16'h3018) || (bad_pll && {hi,lo}==16'h3035) ? 8'h00:value);
            end
        end
    endtask
    task automatic reset_camera;
        begin
            @(negedge clk);force dut.power_count=20'h00000;slave_low=0;repeat(5) @(negedge clk);force dut.power_count=20'hfffff;
        end
    endtask
    task automatic configure_success;
        begin
            register_read(16'h300a,8'h56);register_read(16'h300b,8'h40);
            // One data-phase Don't-Care high with matching readback is valid.
            register_write(0);registers[16'h3103]=8'h11;
            register_read(16'h3103,8'h11);
            repeat(262) register_write(1);
            // Verify the complete setup before waking the sensor, then after.
            register_read(16'h3808,registers[16'h3808]);register_read(16'h3809,registers[16'h3809]);
            register_read(16'h380a,registers[16'h380a]);register_read(16'h380b,registers[16'h380b]);
            register_read(16'h4300,registers[16'h4300]);register_read(16'h501f,registers[16'h501f]);
            register_read(16'h4740,registers[16'h4740]);
            register_write(1);
            if(registers[16'h3808]!==8'h02 || registers[16'h3809]!==8'h80 ||
                registers[16'h380a]!==8'h01 || registers[16'h380b]!==8'he0 ||
                registers[16'h4300]!==8'h6f || registers[16'h501f]!==8'h01 ||
                registers[16'h4740]!==8'h23 || registers[16'h3017]!==8'h7f ||
                registers[16'h3018]!==8'hf0 || registers[16'h3008]!==8'h02) $fatal(1,"Wrong final VGA RGB565 settings");
            if(registers[16'h3035]!==8'h21 || registers[16'h3036]!==8'h60 ||
                registers[16'h3037]!==8'h13 || registers[16'h3108]!==8'h01 ||
                registers[16'h380c]!==8'h07 || registers[16'h380d]!==8'h90 ||
                registers[16'h380e]!==8'h04 || registers[16'h380f]!==8'h40 ||
                registers[16'h3a08]!==8'h00 || registers[16'h3a09]!==8'hf7 ||
                registers[16'h3a0a]!==8'h00 || registers[16'h3a0b]!==8'hcd ||
                registers[16'h3a0e]!==8'h04 || registers[16'h3a0d]!==8'h05)
                $fatal(1,"Wrong clock/exposure candidate or changed geometry");
            // Model one not-yet-effective value, followed by a bounded retry.
            register_read(16'h3808,corrupt ? 8'hff:8'h0a);
            register_read(16'h3808,corrupt ? 8'hff:registers[16'h3808]);
            if(!corrupt) begin
                register_read(16'h3809,registers[16'h3809]);register_read(16'h380a,registers[16'h380a]);
                register_read(16'h380b,registers[16'h380b]);register_read(16'h4300,registers[16'h4300]);
                register_read(16'h501f,registers[16'h501f]);register_read(16'h4740,registers[16'h4740]);
            end
        end
    endtask
    integer core_cycles=0,last_tx_rise=0,checked_bit_periods=0;
    reg previous_tx_rise=0;reg [1:0] previous_byte=0;
    always @(posedge clk)core_cycles=core_cycles+1;
    always @(posedge cam_scl)begin
        #1;
        if(rst_n && dut.camera.bus.state==5)begin
            if(dut.camera.bus.bit_index<7 && previous_tx_rise && previous_byte==dut.camera.bus.byte_index)begin
                // Each released-high phase waits for the existing two-flop
                // sampled-SCL synchronizer, adding two cycles per SCL period.
                if(core_cycles-last_tx_rise!=274)$fatal(1,"Quarter68 not effective: SCL bit period %d",core_cycles-last_tx_rise);
                checked_bit_periods=checked_bit_periods+1;
            end
            last_tx_rise=core_cycles;previous_tx_rise=1;previous_byte=dut.camera.bus.byte_index;
        end else previous_tx_rise=0;
    end
    initial begin
        #1;
        if(dut.camera.I2C_QUARTER_CYCLES!=68 || dut.camera.bus.QUARTER_CYCLES!=68 ||
           dut.camera.DYNAMIC_PAD_MASK!=1 || dut.camera.I2C_TIMEOUT_CYCLES!=1350000)$fatal(1,"SCCB specialization differs");
    end
    initial begin
        #100;reset_camera(); configure_success();wait(ready);#1;
        if(failed || commands_written!==264 || sensor_id!==16'h5640 || verified_write_noacks!=1) $fatal(1,"Initialization status incorrect");
        reset_camera();writes=0;
        register_read(16'h300a,8'h56);register_read(16'h300b,8'h42);wait(failed);#1;
        if(ready || writes!=0 || error_code!==8'h20) $fatal(1,"Wrong silicon must not be configured");
        reset_camera();
        register_read(16'h300a,8'h56);register_read(16'h300b,8'h40);register_write(0);
        register_read(16'h3103,8'hff);wait(failed);#1;
        if(ready || error_code!==8'h70 || failed_address!==16'h3103 || commands_written!=0) $fatal(1,"Unverified write NACK not rejected");
        reset_camera();corrupt=1;configure_success();wait(failed);#1;
        if(ready || error_code!==8'h50 || failed_address!==16'h3808 || observed_value!==8'hff || expected_value!==8'h02) $fatal(1,"Readback mismatch not rejected");
        reset_camera();bad_pad=1;corrupt=0;
        register_read(16'h300a,8'h56);register_read(16'h300b,8'h40);
        repeat(263) register_write(1);wait(failed);#1;
        if(ready || error_code!==8'h70 || failed_address!==16'h3018 || commands_written!=262)
            $fatal(1,"Acknowledged pad write mismatch not rejected at its source");
        reset_camera();bad_pad=0;bad_pll=1;
        register_read(16'h300a,8'h56);register_read(16'h300b,8'h40);
        repeat(251) register_write(1);wait(failed);#1;
        if(ready || error_code!==8'h70 || failed_address!==16'h3035 || commands_written!=250 ||
            observed_value!==8'h00 || expected_value!==8'h21)
            $fatal(1,"System divider readback mismatch was not quarantined");
        reset_camera();bad_pll=0;pad_address_nack=1;
        register_read(16'h300a,8'h56);register_read(16'h300b,8'h40);
        repeat(263)register_write(1);wait(failed);#1;
        if(ready || error_code!==8'h61 || failed_address!==16'h3018 || commands_written!=262 ||
           registers[16'h3017]!==8'h7f || registers[16'h3018]!==8'hf0)
            $fatal(1,"3018 device-address NACK was bypassed or output bits removed");
        reset_camera();pad_address_nack=0;writes=0;
        get_start();expect_byte(8'h78,0);wait(failed);#1;
        if(ready || writes!=0 || commands_written!=0 || error_code!==8'h11 || failed_address!==16'h300a)
            $fatal(1,"ID address NACK was not rejected");
        if(cam_rst_n!==1'b1 || cam2_hold_rst_n!==1'b0)$fatal(1,"Main reset not released or other reset not held");
        clock_enabled=0;#1000;
        if(cam2_hold_rst_n!==1'b0)$fatal(1,"Held reset depends on running27 clock");
        force dut.power_count=20'h00000;#1000;
        if(cam2_hold_rst_n!==1'b0)$fatal(1,"Held reset released during board reset/clock halt");
        $display("PASS actual board sink: power/reset/success/wrongID/write/readback/3018NACK/IDNACK/clock-halt all held0; opaqueDDR/PLL/ADC stubbed, no physical voltage inference.");
        if(checked_bit_periods<1000)$fatal(1,"Insufficient actual SCL periods observed");
        $display("PASS SCCB68 actual consecutive TX bit period=274 core cycles, nominal quarter=68 plus unchanged sampled-SCL synchronization.");
        $display("PASS CAM1 isolated actual top: complete264 writes/full7FF0, PLL/format preserved, wrongID/ID NACK/3018 address NACK61/3018 mismatch70 fail closed.");$finish;
    end
    initial begin #(64'd2000000000);$fatal(1,"Camera init timeout");end
endmodule
