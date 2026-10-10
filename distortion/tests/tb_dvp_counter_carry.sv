`timescale 1ns/1ps
module tb_dvp_counter_carry;
    reg pclk=0;always #5 pclk=~pclk;
    reg rst=1,vsync=0,href=0;
    reg [7:0] data=0;
    wire pixel_valid,frame_start,line_end,odd_line_error;
    wire [15:0] pixel;
    wire [31:0] frame_count,last_frame_pixels;
    dvp_rgb565_capture dut(.*);
    task automatic frame;
        begin
            @(negedge pclk);vsync=1;
            repeat(2) @(negedge pclk);vsync=0;
            repeat(2) @(negedge pclk);
        end
    endtask
    initial begin
        repeat(4) @(negedge pclk);rst=0;frame();
        href=1;
        repeat(65537) begin data=8'h01;@(negedge pclk);data=8'h02;@(negedge pclk);end
        href=0;repeat(3) @(negedge pclk);frame();
        if(last_frame_pixels!=65537 || frame_count!=2 || odd_line_error)
            $fatal(1,"Pixel split carry wrong %d",last_frame_pixels);
        repeat(65534) frame();
        if(frame_count!=65536) $fatal(1,"Frame split carry wrong %d",frame_count);
        $display("PASS DVP counters across 16-bit carry with 65537 pixels and 65536 frames");$finish;
    end
    initial begin #10000000;$fatal(1,"Counter test timeout");end
endmodule
