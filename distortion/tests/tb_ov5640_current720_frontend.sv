`timescale 1ns/1ps
// One complete real-controller initialization plus two full-size synthetic
// nominal720p15 timing frames; clock halt must revoke admission independently.
module tb_ov5640_current720_frontend;
    reg ref_clk=0,pclk=0,pclk_run=1,rst_n=0;
    always #18.519 ref_clk=~ref_clk;
    realtime pclk_half=11.905;
    initial if($test$plusargs("pclk_upper"))pclk_half=10.582;
    always #(pclk_half) if(pclk_run)pclk=~pclk;
    reg vsync_active=0,href_active=0,slave_low=0;
    tri1 cam_rst_n,cam_scl,cam_sda;
    assign cam_sda=slave_low ? 1'b0:1'bz;
    wire configured,raw_authorize,failed;
    wire [7:0] fault,init_error,monitor_fault;
    wire [15:0] sensor_id,failed_address,last_frame_lines,last_line_bytes;
    wire [31:0] good_frames,bad_frames,pclk_edges_per_window;
    wire pclk_fresh,vsync_fresh,href_fresh,frame_fresh,snapshot_fresh;
    wire [7:0] observed_value,expected_value;
    wire observed_valid,final_wake_verified;
    wire [3:0] last_bus_error;
    wire [9:0] action_index,failed_action,writes_completed,verified_write_noacks;
    ov5640_current720_frontend #(.INIT_RESET_CYCLES(8),.INIT_WAIT_CYCLES(12),.MS_CYCLES(2),
        .ACTIVITY_WINDOW_REF_CYCLES(64),.SNAPSHOT_INTERVAL_REF_CYCLES(64),
        .MAX_PCLK_IDLE_REF_CYCLES(64),.MAX_FRAME_IDLE_REF_CYCLES(3000000),.MAX_SNAPSHOT_IDLE_REF_CYCLES(512)) dut(.*);
    reg [7:0] registers[0:65535];
    task defaults;
        begin
            for(integer n=0;n<65536;n=n+1)registers[n]=0;
            registers[16'h300a]=8'h56;registers[16'h300b]=8'h40;registers[16'h3008]=2;
            registers[16'h3034]=8'h1a;registers[16'h3035]=8'h11;registers[16'h3036]=8'h69;
            registers[16'h3037]=3;registers[16'h3103]=3;registers[16'h3108]=1;
        end
    endtask
    task get_start;
        begin do @(negedge cam_sda);while(cam_scl!==1);end
    endtask
    task get_byte(output reg [7:0] value);
        begin
            value=0;repeat(8)begin @(posedge cam_scl);value={value[6:0],cam_sda};end
            @(negedge cam_scl);slave_low=1;@(posedge cam_scl);@(negedge cam_scl);slave_low=0;
        end
    endtask
    task expect_byte(input [7:0] expected);
        reg [7:0] value;
        begin get_byte(value);if(value!==expected)$fatal(1,"720frontend wire byte differs");end
    endtask
    task reply(input [7:0] value);
        begin
            for(integer b=7;b>=0;b=b-1)begin slave_low=!value[b];@(posedge cam_scl);@(negedge cam_scl);end
            slave_low=0;@(posedge cam_scl);if(cam_sda!==1)$fatal(1,"Missing read NACK");@(negedge cam_scl);
        end
    endtask
    reg read_transaction;reg [7:0] hi,lo,value;
    initial forever begin
        get_start();read_transaction=dut.initializer.read_mode;
        expect_byte(8'h78);get_byte(hi);get_byte(lo);
        if(read_transaction)begin get_start();expect_byte(8'h79);reply(registers[{hi,lo}]);end
        else begin get_byte(value);if({hi,lo}==16'h3008 && value[7])defaults();else registers[{hi,lo}]=value;end
    end
    task full_frame;
        begin
            @(negedge pclk);vsync_active=1;href_active=0;repeat(8)@(negedge pclk);vsync_active=0;
            for(integer row=0;row<720;row=row+1)begin
                href_active=1;
                if($test$plusargs("bad_line") && row==0)repeat(2558)@(negedge pclk);
                else repeat(2560)@(negedge pclk);
                href_active=0;
                // HTS1892 is two byte clocks per timing unit:3784-2560.
                repeat(1224)@(negedge pclk);
            end
            repeat(20*3784-8)@(negedge pclk);
        end
    endtask
    initial begin
        defaults();repeat(8)@(negedge ref_clk);rst_n=1;
        if(dut.STARTUP_REF_CYCLES!=27000000)$fatal(1,"Production one-second startup grace changed");
        wait(configured);#1;
        if(failed || raw_authorize || init_error || sensor_id!==16'h5640 ||
           !final_wake_verified || action_index!=402 || !writes_completed)
            $fatal(1,"Register completion incorrectly authorized raw or diagnostics missing");
        $display("PASS frontend configured remains disarmed before live geometry");
        full_frame();
        if($test$plusargs("bad_line"))begin
            repeat(1024)@(negedge ref_clk);
            if(!configured || raw_authorize || !failed || monitor_fault!==8'h12 || init_error)
                $fatal(1,"Malformed first line did not block admission fault=%h",monitor_fault);
            $display("PASS CURRENT720 frontend malformed line blocks admission despite configured registers");
            $finish;
        end
        fork
            full_frame();
            begin
                wait(good_frames==1);#1;
                repeat(128)@(negedge ref_clk);
                if(raw_authorize || failed)$fatal(1,"One frame granted admission or failed");
                $display("PASS frontend one complete good frame remains disarmed");
            end
        join
        @(negedge pclk);vsync_active=1;repeat(8)@(negedge pclk);vsync_active=0;
        // Only the second complete frame's coherent snapshot may authorize.
        wait(raw_authorize && good_frames>=2);#1;
        if(failed || bad_frames || good_frames<2 || last_frame_lines!=720 || last_line_bytes!=2560 ||
           !pclk_fresh || !vsync_fresh || !href_fresh || !frame_fresh || !snapshot_fresh ||
           pclk_edges_per_window<80 || pclk_edges_per_window>120)
            $fatal(1,"Full720 fresh qualification differs good=%0d bad=%0d lines=%0d bytes=%0d edges=%0d fresh=%b%b%b%b%b fault=%h",good_frames,bad_frames,last_frame_lines,last_line_bytes,pclk_edges_per_window,pclk_fresh,vsync_fresh,href_fresh,frame_fresh,snapshot_fresh,fault);
        $display("PASS frontend full2560x720 lines and PCLK-domain edge accounting; two fresh frames");
        @(negedge pclk);pclk_run=0;
        repeat(1024)@(negedge ref_clk);
        if(raw_authorize || !failed || !configured || init_error || !monitor_fault)$fatal(1,"PCLK stop did not revoke despite configured registers");
        repeat(64)@(negedge ref_clk);
        if(raw_authorize || !failed)$fatal(1,"Clock-stop fault was not sticky");
        // Restarting PCLK cannot clear the sticky fault or auto-rearm capture.
        pclk_run=1;repeat(1024)@(negedge ref_clk);
        if(raw_authorize || !failed || !configured)$fatal(1,"Restart cleared sticky clock fault");
        $display("PASS frontend resumed PCLK cannot clear sticky failure");
        $display("PASS CURRENT720 frontend: two complete full-size good frames required, diagnostics and sticky clock-stop failure; synthetic only, no hardware acceptance.");$finish;
    end
    initial begin #(64'd1500000000);$fatal(1,"Bounded720 frontend test timeout");end
endmodule
