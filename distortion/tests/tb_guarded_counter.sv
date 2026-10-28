`timescale 1ns/1ps
// Isolate the boot-global completion counter and identity admission gate;
// in-flight completion/grant feedback are forced digital fixtures only.
module tb_guarded_counter;
    reg clk=0;always #4 clk=~clk;
    reg rst_n=0;reg [95:0] camera_info=0;
    wire [31:0] completed_frames;wire ready_for_grant;
    guarded_capture_controller #(.WIDTH(32),.HEIGHT(16)) dut(
        .core_clk(clk),.cam_clk(clk),.rst_n(rst_n),.camera_ready(1'b1),.ddr_ready(1'b1),
        .warmup_ready(1'b1),.safety_ok(1'b1),.safety_snapshot_valid(1'b1),.safety_snapshot_age(0),
        .temp_valid(1'b1),.temp_failed(1'b0),.temp_over(1'b0),.temp_fault(0),.temp_alarm(0),
        .temp_raw(16'hb000),.temp_code(12'hb00),.temp_age(0),.temp_samples(10),.temp_conversions(12),
        .camera_info(camera_info),.rx_valid(1'b0),.rx_data(8'b0),.rx_framing_error(1'b0),
        .vsync(1'b0),.href(1'b0),.data(8'b0),.awready(1'b0),.arready(1'b0),.wready(1'b0),.wlast(1'b0),
        .rdata(256'b0),.rvalid(1'b0),.rlast(1'b0),.rid(4'b0),.byte_ready(1'b1),.byte_done(1'b0),
        .completed_frames(completed_frames),.ready_for_grant(ready_for_grant));
    task tick;begin @(posedge clk);#1;end endtask
    initial begin
        force dut.raw_done=0;force dut.grant_accepted=0;force dut.core_idle=1;
        force dut.raw_failed=0;force dut.requires_reset=0;
        repeat(3)tick;@(negedge clk);rst_n=1;tick;
        if(ready_for_grant)$fatal(1,"missing camera identity admitted a grant");
        camera_info=(96'd1<<81)|16'h5640;#1;
        if(!ready_for_grant)$fatal(1,"valid ready sensor identity was rejected");
        camera_info[80]=1;#1;if(ready_for_grant)$fatal(1,"failed camera allowed grant");
        camera_info[80]=0;camera_info[15:0]=16'h1234;#1;if(ready_for_grant)$fatal(1,"wrong sensor ID allowed grant");
        camera_info[15:0]=16'h5640;
        force dut.raw_done=1;tick;force dut.raw_done=0;
        if(completed_frames!=1)$fatal(1,"completion not counted");
        force dut.grant_accepted=1;tick;
        if(completed_frames!=1)$fatal(1,"new grant reset global completion evidence");
        force dut.raw_done=1;tick;force dut.raw_done=0;
        if(completed_frames!=2)$fatal(1,"simultaneous grant erased completion");
        force dut.grant_accepted=0;tick;
        force dut.grant_accepted=1;tick;force dut.grant_accepted=0;
        if(completed_frames!=2)$fatal(1,"later grant regressed completion counter");
        @(negedge clk);rst_n=0;tick;
        if(completed_frames!=0)$fatal(1,"shared reset did not reset completion counter");
        $display("PASS guarded global completion counter and camera-5640 identity admission gate: grants preserve completed count; reset clears it.");
        $finish;
    end
    initial begin #100000;$fatal(1,"counter test watchdog");end
endmodule
