`timescale 1ns/1ps
module tb_dvp_monitor;
    reg sysclk=0,pclk=0,rst_n=0,vsync=0,href=0;
    always #5 sysclk=~sysclk;
    always #7 pclk=~pclk;
    reg [7:0] data=0;
    wire [23:0] edges_per_window;
    wire [31:0] frames,last_pixels,last_checksum;
    wire [15:0] last_lines,pixel;
    wire last_odd,pixel_valid,frame_start;
    dvp_monitor #(.WINDOW_CYCLES(100)) dut(.*);
    integer seen=0;
    function [31:0] expected_checksum;
        input integer n;
        integer i;
        begin
            expected_checksum=0;
            for(i=0;i<n;i=i+1) expected_checksum={expected_checksum[30:0],expected_checksum[31]} ^ 32'h07e0;
        end
    endfunction
    always @(negedge pclk) if(rst_n && pixel_valid) begin
        if(pixel!==16'h07e0) $fatal(1,"RGB565 low-byte-first decoding failed");
        seen=seen+1;
    end
    task automatic sync_frame;
        begin
            @(negedge pclk);vsync=1;repeat(3) @(negedge pclk);vsync=0;
            repeat(4) @(negedge pclk);
        end
    endtask
    task automatic line(input bit odd_byte);
        begin
            @(negedge pclk);href=1;
            repeat(4) begin data=8'he0;@(negedge pclk);data=8'h07;@(negedge pclk);end
            if(odd_byte) begin data=8'h55;@(negedge pclk);end
            href=0;repeat(5) @(negedge pclk);
        end
    endtask
    initial begin
        #101;rst_n=1;repeat(5) @(negedge pclk);
        sync_frame();line(0);line(0);sync_frame();
        repeat(12) @(posedge sysclk);#1;
        if(frames!=2 || last_pixels!=8 || last_lines!=2 || last_odd || seen!=8 || last_checksum!=expected_checksum(8))
            $fatal(1,"Frame snapshot incoherent F=%d P=%d L=%d O=%b",frames,last_pixels,last_lines,last_odd);
        line(1);sync_frame();repeat(12) @(posedge sysclk);#1;
        if(frames!=3 || last_pixels!=4 || last_lines!=1 || !last_odd || last_checksum!=expected_checksum(4)) $fatal(1,"Odd line metadata lost");
        repeat(400) @(posedge sysclk);#1;
        if(edges_per_window<70 || edges_per_window>73) $fatal(1,"Gray edge counter crossing failed %d",edges_per_window);
        $display("PASS dvp_monitor asynchronous clocks, coherent frame snapshots, RGB565 little endian, odd line and edge-rate measurement");$finish;
    end
    initial begin #100000;$fatal(1,"Monitor timeout");end
endmodule
