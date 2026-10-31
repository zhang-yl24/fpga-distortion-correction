`timescale 1ps/1fs
module tb_processed_output_pattern;
`ifdef NATIVE
    localparam W=1920,H=1080,HT=2200,VT=1125,VS=5,X0=192,Y0=41;
`else
    localparam W=64,H=32,HT=80,VT=42,VS=2,X0=8,Y0=5;
`endif
    reg clk=0,rst_n=0,enable=0;
    // 27MHz, with femtosecond rational rounding; no accelerated clock.
    always #18518.518519 clk=~clk;
    wire vsync_active,de;wire [23:0] rgb;wire [31:0] frame_counter;
    processed_output_pattern #(.WIDTH(W),.HEIGHT(H),.HT(HT),.VT(VT),.VS(VS),.X0(X0),.Y0(Y0)) dut(
        .clk(clk),.rst_n(rst_n),.enable(enable),.vsync_active(vsync_active),.de(de),.rgb(rgb),.frame_counter(frame_counter));
    reg [23:0] expected[0:W*H-1];
    integer pixels_checked=0,rasters_checked=0,reset_checks=0,fd;
    task automatic check_idle(input integer count,input integer expected_id);
        integer n;
        begin
            for(n=0;n<count;n=n+1)begin
                @(negedge clk);
                if(vsync_active!==0 || de!==0 || rgb!==0 || frame_counter!==expected_id)
                    $fatal(1,"idle output/counter changed id=%0d",expected_id);
            end
        end
    endtask
    task automatic await_start(input integer expected_id);
        integer limit;
        begin
            limit=0;
            while(frame_counter!=expected_id && limit<12)begin @(negedge clk);limit=limit+1;end
            if(frame_counter!==expected_id)$fatal(1,"source did not start expected frame%0d",expected_id);
        end
    endtask
    // Start sampling at coordinate0,0 on the current falling edge. Reference
    // coordinates come from elapsed output clocks, never the DUT's counters.
    task automatic check_raster(input integer expected_id,input integer drop_at,input integer limit);
        integer k,x,y,active,pixels;
        reg [23:0] want;
        begin
            pixels=0;
            for(k=0;k<limit;k=k+1)begin
                if(k!=0)@(negedge clk);
                x=k%HT;y=k/HT;
                active=x>=X0 && x<X0+W && y>=Y0 && y<Y0+H;
                want=active ? expected[(y-Y0)*W+x-X0]:24'd0;
                if(vsync_active!==(y<VS) || de!==active[0] || rgb!==want || frame_counter!==expected_id)
                    $fatal(1,"raster mismatch frame=%0d at%0d,%0d vs=%b de=%b rgb=%h want=%h",expected_id,x,y,vsync_active,de,rgb,want);
                if(active)begin
                    if(rgb===0)$fatal(1,"active pattern contains a black pixel");
                    pixels=pixels+1;pixels_checked=pixels_checked+1;
                end
                if(k==drop_at)enable=0;
            end
            if(limit==HT*VT)begin
                if(pixels!=W*H)$fatal(1,"full raster pixel count differs");
                rasters_checked=rasters_checked+1;
            end
        end
    endtask
    initial begin
        $readmemh("expected-rgb.mem",expected);
        repeat(3)@(negedge clk);rst_n=1;
        check_idle(5,0);
        enable=1;await_start(1);
        check_raster(1,HT*VT/2,HT*VT);
        check_idle(12,1);
`ifndef NATIVE
        // Re-enable starts a new complete raster rather than resuming a
        // coordinate; a disabled source retains the last emitted frame ID.
        enable=1;await_start(2);
        check_raster(2,HT*VT/3,HT*VT);
        check_idle(5,2);
        enable=1;await_start(3);
        check_raster(3,-1,HT*VT/4);
        // Assert away from a clock edge. Outputs must become inactive before
        // another rising edge; release must wait for the local two-flop chain.
        #2000 rst_n=0;#1;
        if(vsync_active!==0 || de!==0 || rgb!==0 || frame_counter!==0)$fatal(1,"asynchronous reset assertion failed");
        reset_checks=reset_checks+1;
        repeat(2)@(negedge clk);rst_n=1;
        @(posedge clk);#1;
        if(frame_counter!==0 || de!==0 || vsync_active!==0)$fatal(1,"reset released on first synchronization edge");
        @(posedge clk);#1;
        if(frame_counter!==0 || de!==0 || vsync_active!==0)$fatal(1,"reset released on second synchronization edge");
        @(negedge clk);await_start(1);
        check_raster(1,HT*VT/2,HT*VT);
        check_idle(8,1);
`endif
        fd=$fopen("summary.json","w");
        $fdisplay(fd,"{\"Passed\":true,\"Width\":%0d,\"Height\":%0d,\"ClockHz\":27000000,\"FullRasters\":%0d,\"PixelsCompared\":%0d,\"MidFrameDisableCompleted\":true,\"AsyncResetChecks\":%0d}",W,H,rasters_checked,pixels_checked,reset_checks);
        $fclose(fd);
        $display("PROCESSED_OUTPUT_PATTERN_PASS width=%0d height=%0d rasters=%0d pixels=%0d",W,H,rasters_checked,pixels_checked);
        $finish;
    end
    initial begin
        repeat(4*HT*VT+200)@(posedge clk);
        $fatal(1,"bounded pattern test timeout");
    end
endmodule
