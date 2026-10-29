`timescale 1ns/1ps
// Actual delayed diagnostic top, explicit interface-matched control stubs.
// This checks reset ordering only: no real I2C, UART bytes, PLL or video timing.
// The existing 20-bit cold-power counter is forced to its terminal value after
// checking UART activity; its million-cycle duration is NOT this test's target.
module tb_hdmi_diag_startup;
    localparam SETTLE=12;
    reg clk_27m=0, reset_n=0;
    always #5 clk_27m=~clk_27m;
    tri1 hd_scl,hd_sda;
    wire rstn_out,uart_txd,pix_clk,hs_out,vs_out,de_out;
    wire [7:0] r_out,g_out,b_out,led;
    hdmi_uart_delayed_diag #(.CFG_SETTLE_CYCLES(SETTLE)) dut(.*);
    integer requests=0, cases=0, cycles_after_g25=0;
    reg last_g25=0;
    always @(posedge clk_27m) begin
        // NBA updates to power_ready/rstn_out occur after this sampling edge.
        if(!rstn_out) cycles_after_g25=0;
        else cycles_after_g25=cycles_after_g25+1;
    end
    always @(posedge dut.hdmi_configuration.first_request) begin
        requests=requests+1;
        if(!rstn_out || !dut.configuration_reset_n || cycles_after_g25<SETTLE)
            $fatal(1,"first configuration request escaped the post-G25 delay cycles=%0d",cycles_after_g25);
    end
    always @(negedge reset_n) begin
        #1;
        if(rstn_out || dut.configuration_reset_n || dut.configuration_ready)
            $fatal(1,"manual reset did not asynchronously assert both chip/config resets");
    end
    task automatic mark(input string name);
        begin cases=cases+1; $display("HDMI_STARTUP_CASE %s PASS",name); end
    endtask
    task automatic release_power;
        integer activity_before;
        begin
            @(negedge clk_27m); reset_n=1;
            repeat(8) @(negedge clk_27m);
            activity_before=dut.telemetry.active_ticks;
            repeat(5) @(negedge clk_27m);
            if(rstn_out || dut.configuration_reset_n || !dut.telemetry.rst_n ||
               dut.telemetry.active_ticks<=activity_before)
                $fatal(1,"UART held by peripheral/config reset or config escaped before G25");
            force dut.power_count=20'hfffff;
            @(posedge clk_27m); #1; release dut.power_count;
            if(!rstn_out || dut.configuration_reset_n || dut.configuration_wait_count!=0)
                $fatal(1,"G25 release did not start a fresh configuration delay");
        end
    endtask
    task automatic verify_full_wait;
        integer old_requests, activity_before;
        begin
            old_requests=requests; activity_before=dut.telemetry.active_ticks;
            for(integer i=1;i<=SETTLE;i=i+1) begin
                @(posedge clk_27m); #1;
                if(!rstn_out || !dut.telemetry.rst_n)
                    $fatal(1,"G25 or UART reset changed during config settle");
                if(i<SETTLE && (dut.configuration_reset_n || requests!=old_requests))
                    $fatal(1,"configuration released early at cycle%0d",i);
                if(i==SETTLE && !dut.configuration_reset_n)
                    $fatal(1,"configuration failed to release at exact settle deadline");
            end
            if(dut.telemetry.active_ticks<=activity_before || !dut.pattern.rst_n)
                $fatal(1,"configuration wait incorrectly delayed UART or pattern");
            repeat(5) @(negedge clk_27m);
            if(requests!=old_requests+1 || dut.hdmi_configuration.completed_transactions!=1)
                $fatal(1,"stub did not issue exactly one request after release");
        end
    endtask
    initial begin
        repeat(5) @(negedge clk_27m);
        release_power(); verify_full_wait();
        mark("g25_then_exact_settle_before_first_request");
        mark("uart_and_pattern_continue_during_configuration_hold");

        // A sticky configuration failure is observed, never used as a reset
        // or automatic retry source by this top-level delay experiment.
        @(negedge clk_27m); dut.hdmi_configuration.inject_failure=1;
        repeat(3*SETTLE) @(negedge clk_27m);
        if(!rstn_out || !dut.configuration_reset_n || !dut.cfg_failed ||
           dut.cfg_error!=1 || requests!=1 || dut.hdmi_configuration.completed_transactions!=1)
            $fatal(1,"configuration fault restarted the delay/controller");
        mark("failure_does_not_trigger_automatic_retry");

        @(negedge clk_27m); reset_n=0;
        repeat(4) @(negedge clk_27m);
        dut.hdmi_configuration.inject_failure=0;
        release_power(); verify_full_wait();
        if(requests!=2) $fatal(1,"manual reset after release missed full reinitialization");
        mark("manual_reset_after_release_requires_full_delay_again");

        @(negedge clk_27m); reset_n=0;
        repeat(4) @(negedge clk_27m);
        release_power();
        repeat(SETTLE/2) @(negedge clk_27m);
        if(dut.configuration_reset_n || requests!=2) $fatal(1,"half-delay precondition invalid");
        reset_n=0;
        repeat(4) @(negedge clk_27m);
        release_power(); verify_full_wait();
        if(requests!=3) $fatal(1,"manual reset during wait retained partial elapsed time");
        mark("manual_reset_during_hold_restarts_full_delay");
        if(cases!=5) $fatal(1,"startup coverage incomplete");
        $display("HDMI_STARTUP_SUMMARY cases=%0d first_requests=%0d settle_cycles=%0d",cases,requests,SETTLE);
        $display("PASS hdmi_diag_startup"); $finish;
    end
    initial begin #20000; $fatal(1,"HDMI startup bounded timeout"); end
endmodule

// Test-only generated-clock stand-ins. Deliberately asynchronous to ref_clk;
// neither lock timing nor actual frequencies are under test here.
module cfg_pll(input clkin1,output clkout0,output lock);
    reg clock=0; always #7 clock=~clock;
    assign clkout0=clock; assign lock=1'b1;
endmodule
module bringup_pll(input clkin1,output clkout0,output lock);
    reg clock=0; always #3 clock=~clock;
    assign clkout0=clock; assign lock=1'b1;
endmodule

module ms72xx_observed_ctl #(
    parameter integer CLK_FRE=10000000,IIC_FREQ=400000,TIMEOUT_CYCLES=CLK_FRE/100
)(input clk,rst_n,output init_over_rx,init_over,init_failed,output [3:0] error_code,
  inout iic_scl,iic_sda,output reg [31:0] completed_transactions,
  output [15:0] last_address,output [7:0] last_value,output [1:0] last_meta);
    reg issued=0,first_request=0,inject_failure=0;
    always @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin issued<=0; first_request<=0; completed_transactions<=0; end
        else begin
            first_request<=0;
            if(!issued) begin issued<=1; first_request<=1; completed_transactions<=1; end
        end
    end
    assign iic_scl=first_request ? 1'b0 : 1'bz;
    assign iic_sda=1'bz;
    assign init_over_rx=rst_n && issued && !inject_failure;
    assign init_over=init_over_rx;
    assign init_failed=rst_n && inject_failure;
    assign error_code=init_failed ? 4'h1 : 4'h0;
    assign last_address=issued ? 16'h0003 : 16'h0;
    assign last_value=issued ? 8'h5a : 8'h0;
    assign last_meta=0;
endmodule

module video_pattern #(parameter MODE_720P=1)(input clk,rst_n,
    output hs,vs,de,output [7:0] r,g,b);
    assign hs=rst_n; assign vs=rst_n; assign de=rst_n;
    assign r=rst_n ? 8'h12 : 8'h00;
    assign g=rst_n ? 8'h34 : 8'h00;
    assign b=rst_n ? 8'h56 : 8'h00;
endmodule

module hdmi_diag_uart #(
    parameter integer REF_CLOCK_HZ=27000000,BAUD=115200,
    REPORT_CYCLES=REF_CLOCK_HZ/2,CFG_SNAPSHOT_CYCLES=REF_CLOCK_HZ/1000,
    CFG_STALE_CYCLES=REF_CLOCK_HZ/100
)(input ref_clk,cfg_clk,rst_n,
  input cfg_rx_done,cfg_all_done,cfg_failed,input [3:0] cfg_error,
  input [31:0] cfg_transactions,input [15:0] cfg_last_address,
  input [7:0] cfg_last_value,input [1:0] cfg_last_meta,
  input cfg_lock_ref,video_lock_ref,observer_released,input_qualified,input_failed,
  input [7:0] input_fault,input polarity_known_ref,vs_inactive_ref,hs_inactive_ref,
  input [15:0] measured_width,measured_height,
  input [31:0] pclk_edges_per_window,good_frames,bad_frames,
  output uart_txd,record_started,record_done,output [31:0] record_sequence);
    integer active_ticks=0;
    always @(posedge ref_clk or negedge rst_n)
        if(!rst_n) active_ticks<=0; else active_ticks<=active_ticks+1;
    assign uart_txd=rst_n ? active_ticks[0] : 1'b1;
    assign record_started=0; assign record_done=0; assign record_sequence=0;
endmodule
