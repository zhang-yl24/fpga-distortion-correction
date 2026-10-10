`timescale 1ns/1ps
module tb_rgb565_burst_pack_early;
    reg clk=0;always #5 clk=~clk;
    reg rst_n=0,frame_start=0,line_end=0,pixel_valid=0,beat_ready=0;
    reg [15:0] pixel=0;
    wire beat_valid,beat_first,beat_last,frame_complete,frame_invalid,overflow_seen;
    wire [255:0] beat_data;wire [31:0] beat_byte_offset,dropped_frames;
    rgb565_burst_pack_early #(.WIDTH(32),.HEIGHT(2)) dut(.*);
    integer beats=0,phase=0,completions=0;
    always @(posedge clk) if(rst_n && frame_complete) completions=completions+1;
    reg previous_stall=0;reg [289:0] previous_beat;
    wire [289:0] whole_beat={beat_data,beat_byte_offset,beat_first,beat_last};
    always @(posedge clk) begin
        if(rst_n) begin
            if(previous_stall && (!beat_valid || whole_beat!==previous_beat))
                $fatal(1,"Stalled beat changed");
            if(beat_valid && beat_ready) begin
                if(phase==0 || phase==3) begin
                    if(beat_byte_offset!==beats*32 || beat_first!==(beats==0) || beat_last!==(beats==3))
                        $fatal(1,"Beat address/flags %0d",beats);
                    for(integer i=0;i<16;i=i+1)
                        if(beat_data[i*16+:16]!==16'h1000+beats*16+i)
                            $fatal(1,"Pixel lane/order mismatch");
                end
                beats=beats+1;
            end
        end
        previous_stall=rst_n && beat_valid && !beat_ready;previous_beat=whole_beat;
    end
    task automatic pulse_frame;
        begin @(negedge clk);frame_start=1;@(negedge clk);frame_start=0;end
    endtask
    task automatic send_pixel(input [15:0] p,input integer gap);
        begin @(negedge clk);pixel=p;pixel_valid=1;
            @(negedge clk);pixel_valid=0;repeat(gap) @(negedge clk);end
    endtask
    task automatic end_line;
        begin @(negedge clk);line_end=1;@(negedge clk);line_end=0;end
    endtask
    task automatic send_frame;
        begin
            for(integer y=0;y<2;y=y+1) begin
                for(integer x=0;x<32;x=x+1) send_pixel(16'h1000+y*32+x,x%3);
                end_line();
            end
        end
    endtask
    initial begin
        repeat(4) @(negedge clk);rst_n=1;beat_ready=1;
        pulse_frame();send_frame();repeat(4) @(negedge clk);
        if(beats!=4) $fatal(1,"Missing complete-frame beats");
        @(negedge clk);frame_start=1;@(negedge clk);
        if(completions!=1 || frame_complete || dropped_frames!=0) $fatal(1,"Good frame not completed");frame_start=0;
        // A long DDR/FIFO stall must invalidate one frame, hold the old beat,
        // and ignore subsequent sensor pixels until the next VSYNC.
        phase=1;beat_ready=0;
        for(integer i=0;i<32;i=i+1) send_pixel(i,0);
        if(dropped_frames!=1 || !overflow_seen || !beat_valid) $fatal(1,"Overflow handling incorrect");
        repeat(5) @(negedge clk);beat_ready=1;repeat(5) @(negedge clk);
        phase=2;pulse_frame();send_pixel(1,0);end_line();
        if(dropped_frames!=2) $fatal(1,"Short line was not rejected");
        phase=3;beats=0;pulse_frame();send_frame();repeat(4) @(negedge clk);
        @(negedge clk);frame_start=1;@(negedge clk);
        if(completions!=2 || frame_complete || beats!=4 || dropped_frames!=2) $fatal(1,"Recovery failed");
        frame_start=0;phase=4;beat_ready=1;
        for(integer x=0;x<32;x=x+1) send_pixel(x,0);
        end_line();
        for(integer x=0;x<16;x=x+1) send_pixel(x,0);
        repeat(4) @(negedge clk);beat_ready=0;
        for(integer x=16;x<32;x=x+1) send_pixel(x,0);
        end_line();
        @(negedge clk);frame_start=1;@(negedge clk);
        if(frame_complete || dropped_frames!=4 || !beat_valid || !beat_last)
            $fatal(1,"Unaccepted final beat falsely committed, or new stalled frame not discarded");
        frame_start=0;repeat(4) @(negedge clk);beat_ready=1;repeat(4) @(negedge clk);
        $display("PASS early burst_pack last-line commit, 256-bit lane order/addresses, gapped DVP, stalled output stability, overflow/short-line discard and frame recovery");$finish;
    end
    initial begin #1000000;$fatal(1,"Pack timeout");end
endmodule
